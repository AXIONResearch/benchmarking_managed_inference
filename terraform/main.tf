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

# GCP Compute Instance with 8x L4 24GB GPUs
resource "google_compute_instance" "atomix_bench" {
  name         = "atomix-bench-l4"
  machine_type = "g2-standard-96"  # 8x L4 24GB
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-cu128-ubuntu-2204-nvidia-570"
      size  = 500  # 500GB boot disk
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  # Note: g2-standard-96 comes with 8x L4 24GB GPUs built-in
  # No need to specify guest_accelerator separately

  scheduling {
    on_host_maintenance = "TERMINATE"  # Required for GPU instances
    automatic_restart   = false
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -e

    # Deep Learning VM already has Docker, NVIDIA drivers, and nvidia-container-toolkit
    # Just install Docker Compose and utilities

    # Install Docker Compose
    DOCKER_COMPOSE_VERSION="2.24.0"
    curl -L "https://github.com/docker/compose/releases/download/v$${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    # Install utilities
    apt-get update
    apt-get install -y git htop

    echo "Setup complete! Ready for vLLM deployment."
  EOF

  tags = ["atomix-bench", "http-server", "https-server"]
}

# Firewall rules for vLLM endpoints
resource "google_compute_firewall" "vllm_ports" {
  name    = "atomix-vllm-ports"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8001-8006", "8080", "8081", "22"]
  }

  source_ranges = ["0.0.0.0/0"]  # Restrict this in production
  target_tags   = ["atomix-bench"]
}

output "instance_ip" {
  value       = google_compute_instance.atomix_bench.network_interface[0].access_config[0].nat_ip
  description = "Public IP of the A100 benchmark instance"
}

output "instance_name" {
  value       = google_compute_instance.atomix_bench.name
  description = "Name of the instance"
}

output "instance_info" {
  value = "Instance: ${google_compute_instance.atomix_bench.name} with 8x L4 24GB GPUs (~$8/hour)"
  description = "Instance information"
}
