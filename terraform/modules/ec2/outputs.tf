# Outputs for EC2 Module

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = var.create_instance ? aws_instance.polars_etl[0].id : null
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = var.create_instance ? aws_instance.polars_etl[0].public_ip : null
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = var.create_instance ? aws_instance.polars_etl[0].private_ip : null
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = var.create_instance ? aws_instance.polars_etl[0].public_dns : null
}

output "elastic_ip" {
  description = "Elastic IP address (if allocated)"
  value       = var.create_instance && var.allocate_eip ? aws_eip.polars_etl[0].public_ip : null
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.polars_ec2.id
}

output "iam_role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.polars_ec2.arn
}

output "iam_role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.polars_ec2.name
}

output "instance_profile_arn" {
  description = "ARN of the IAM instance profile"
  value       = aws_iam_instance_profile.polars_ec2.arn
}

output "cloudwatch_log_group" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.polars_etl.name
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value = var.create_instance && var.key_name != null ? (
    var.allocate_eip ?
    "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.polars_etl[0].public_ip}" :
    "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.polars_etl[0].public_ip}"
  ) : "No SSH key configured"
}

output "instance_type" {
  description = "Instance type used"
  value       = var.instance_type
}

output "ami_id" {
  description = "AMI ID used for the instance"
  value       = data.aws_ami.amazon_linux_2023.id
}
