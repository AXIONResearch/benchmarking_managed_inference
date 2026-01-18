variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "instance_name" {
  description = "Name of the compute instance"
  type        = string
  default     = "omri-kvcached"
}

variable "machine_type" {
  description = "GCP machine type"
  type        = string
  default     = "n1-standard-1"
}

variable "gpu_type" {
  description = "Type of GPU accelerator"
  type        = string
  default     = "nvidia-tesla-t4"
}

variable "gpu_count" {
  description = "Number of GPUs to attach"
  type        = number
  default     = 4
}

variable "hf_token" {
  description = "HuggingFace API token for model access"
  type        = string
  sensitive   = true
}
