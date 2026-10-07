/*
 * ECS Fargate (CLAUDE.md §52, §53.1): one cluster, one task definition + service per entry in
 * `var.services` (api, web, worker in practice), and — for services marked `public` — an ALB
 * target group and path-based listener rule. `worker` (the Temporal workflow worker) runs with
 * no target group: nothing calls it over HTTP, it calls out to the Temporal frontend.
 */

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.tags
}

# --- Load balancer -----------------------------------------------------------------------

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  tags = var.tags
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }
}

locals {
  public_services = { for name, svc in var.services : name => svc if svc.public }
}

resource "aws_lb_target_group" "public" {
  for_each = local.public_services

  name        = "${var.name_prefix}-${each.key}"
  port        = each.value.port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = each.value.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 10
    matcher             = "200"
  }

  tags = var.tags
}

resource "aws_lb_listener_rule" "public" {
  for_each = local.public_services

  listener_arn = aws_lb_listener.https.arn
  priority     = 100 + index(keys(local.public_services), each.key)

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.public[each.key].arn
  }

  condition {
    path_pattern {
      values = [each.value.path_pattern]
    }
  }
}

# --- IAM -----------------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid       = "ReadDatabaseAndApplicationSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = concat([var.database_credentials_secret_arn], values(var.application_secret_arns))
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${var.name_prefix}-ecs-execution-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# The task role: what the *application code* can do with the AWS SDK at runtime. Least
# privilege (CLAUDE.md §40) — today that is exactly one thing, reading/writing the tenant
# object-storage bucket (CLAUDE.md §34); nothing else the app does touches an AWS API directly.
data "aws_iam_policy_document" "task" {
  statement {
    sid = "ObjectStorageReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${var.object_storage_bucket_arn}/*"]
  }

  statement {
    sid       = "ObjectStorageListBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.object_storage_bucket_arn]
  }

  # The ADOT collector sidecar (below) ships every task's OpenTelemetry traces/metrics —
  # CLAUDE.md §35's "every request... traced" requirement doesn't stop at the container
  # boundary just because there's no local collector to send them to anymore.
  statement {
    sid = "OpenTelemetryExport"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "cloudwatch:PutMetricData",
      "logs:PutLogEvents",
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "task" {
  name   = "${var.name_prefix}-ecs-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# --- Services --------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "service" {
  for_each = var.services

  name              = "/ecs/${var.name_prefix}/${each.key}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_ecs_task_definition" "service" {
  for_each = var.services

  family                   = "${var.name_prefix}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = each.value.image
      essential = true
      portMappings = [
        { containerPort = each.value.port, protocol = "tcp" }
      ]
      environment = each.value.environment
      secrets = concat(
        [
          { name = "DATABASE_CREDENTIALS", valueFrom = var.database_credentials_secret_arn }
        ],
        [
          for secret_name, arn in var.application_secret_arns :
          { name = upper(replace(secret_name, "-", "_")), valueFrom = arn }
        ]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.service[each.key].name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = each.key
        }
      }
    },
    {
      # The ADOT collector sidecar: `awsvpc` network mode means every container in this task
      # shares one network namespace, so the app's own default `otel_endpoint` of
      # `http://localhost:4317` (`colt_config.Settings`) reaches this container unchanged —
      # no application code or config needs to know it moved from a Docker Compose service to
      # an ECS sidecar.
      name      = "otel-collector"
      image     = "public.ecr.aws/aws-observability/aws-otel-collector:latest"
      essential = false
      command   = ["--config=/etc/ecs/ecs-default-config.yaml"]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.service[each.key].name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "otel-collector"
        }
      }
    }
  ])

  tags = var.tags
}

data "aws_region" "current" {}

resource "aws_ecs_service" "service" {
  for_each = var.services

  name            = "${var.name_prefix}-${each.key}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.service[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.app_security_group_id]
  }

  dynamic "load_balancer" {
    for_each = each.value.public ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.public[each.key].arn
      container_name   = each.key
      container_port   = each.value.port
    }
  }

  # New tasks must pass their health check before the old ones are torn down — zero-downtime
  # deploys (CLAUDE.md §56's deployment-safety requirement), not just the ECS default behavior.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  tags = var.tags

  depends_on = [aws_lb_listener.https]
}
