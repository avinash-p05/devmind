output "api_url" {
  value = "http://${aws_lb.main.dns_name}"
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "api_repository" {
  value = aws_ecr_repository.api.repository_url
}
