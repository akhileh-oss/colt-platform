/*
 * Self-hosted Temporal server on ECS Fargate (CLAUDE.md §53.1's "Temporal infrastructure /
 * managed integration as selected"): this milestone's own documented choice is self-hosting
 * on the same RDS instance the application already uses (`temporalio/auto-setup`, the exact
 * image `docker-compose.yml`'s local `temporal` service already pins), rather than Temporal
 * Cloud — no Temporal Cloud account exists for this project, and self-hosting needs no new
 * external vendor relationship to stand up a staging environment reproducibly from Terraform
 * alone, this milestone's literal acceptance criterion. Production may move to Temporal Cloud
 * later without changing anything `colt-workflows` itself does — it only ever talks to
 * whatever `TEMPORAL_ADDRESS` resolves to.
 *
 * `temporal`/`temporal_visibility` are two more databases on the same Postgres instance
 * `database_host` already runs. Nothing here creates them explicitly — the `auto-setup` image
 * variant (as opposed to the plain `temporal-server` image, which needs a pre-created schema)
 * runs `temporal-sql-tool create-database`/`setup-schema` against `DBNAME`/`VISIBILITY_DBNAME`
 * itself on every container start, the exact mechanism `docker-compose.yml`'s local `temporal`
 * service already relies on against the local `postgres` container. The RDS master user
 * (`database_master_username`) has `CREATEDB` by default, so this needs no extra grant.
 */

resource "aws_service_discovery_private_dns_namespace" "this" {
  name = "${var.name_prefix}.internal"
  vpc  = var.vpc_id
}

resource "aws_service_discovery_service" "temporal" {
  name = "temporal"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.this.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
}

resource "aws_cloudwatch_log_group" "temporal" {
  name              = "/ecs/${var.name_prefix}/temporal"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_ecs_task_definition" "temporal" {
  family                   = "${var.name_prefix}-temporal"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "temporal"
      image     = var.image
      essential = true
      portMappings = [
        { containerPort = 7233, protocol = "tcp" }
      ]
      environment = [
        { name = "DB", value = "postgres12" },
        { name = "DB_PORT", value = tostring(var.database_port) },
        { name = "POSTGRES_SEEDS", value = var.database_host },
        { name = "DBNAME", value = "temporal" },
        { name = "VISIBILITY_DBNAME", value = "temporal_visibility" },
      ]
      secrets = [
        { name = "POSTGRES_USER", valueFrom = "${var.database_credentials_secret_arn}:username::" },
        { name = "POSTGRES_PWD", valueFrom = "${var.database_credentials_secret_arn}:password::" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.temporal.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "temporal"
        }
      }
    }
  ])

  tags = var.tags
}

data "aws_region" "current" {}

resource "aws_ecs_service" "temporal" {
  name            = "${var.name_prefix}-temporal"
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.temporal.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [var.app_security_group_id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.temporal.arn
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}
