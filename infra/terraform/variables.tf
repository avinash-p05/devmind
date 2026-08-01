variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "devmind"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "api_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "frontend_image" {
  type = string
}
