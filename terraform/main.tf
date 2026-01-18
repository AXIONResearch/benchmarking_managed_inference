terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_instance" "kvcached_instance" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 100
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  guest_accelerator {
    type  = var.gpu_type
    count = var.gpu_count
  }

  scheduling {
    on_host_maintenance = "TERMINATE"
    automatic_restart   = false
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    HF_TOKEN = var.hf_token
  })

  tags = ["kvcached", "http-server"]
}

resource "google_compute_firewall" "kvcached_ports" {
  name    = "kvcached-ports"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8001-8005", "8081", "22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["kvcached"]
}

output "instance_ip" {
  value       = google_compute_instance.kvcached_instance.network_interface[0].access_config[0].nat_ip
  description = "Public IP of KVCached instance"
}

output "instance_name" {
  value       = google_compute_instance.kvcached_instance.name
  description = "Name of the instance"
}

output "ssh_command" {
  value       = "gcloud compute ssh --zone ${var.zone} ${google_compute_instance.kvcached_instance.name} --project ${var.project_id}"
  description = "Command to SSH into the instance"
}

output "health_check_url" {
  value       = "http://${google_compute_instance.kvcached_instance.network_interface[0].access_config[0].nat_ip}:8081/health"
  description = "Health check URL for KVCached"
}
