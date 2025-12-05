variable "repositories" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "environment" {
  description = "Environment name"
  type        = string
}
