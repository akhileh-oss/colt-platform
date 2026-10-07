/*
 * A CloudWatch dashboard (CLAUDE.md §35, §53.1) surfacing the same signals the local stack's
 * OTel collector + structured logs make visible in development: ALB request volume/latency/
 * error rate, RDS CPU/connections/storage, and ECS service CPU/memory. Alarms on these same
 * metrics live in the `alerting` module — this module is read-only visualization.
 */

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = "${var.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB requests / errors"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum" }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p99" }],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "RDS"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.database_instance_id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.database_instance_id],
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", var.database_instance_id],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS cluster"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name],
          ]
        }
      },
    ]
  })
}

data "aws_region" "current" {}
