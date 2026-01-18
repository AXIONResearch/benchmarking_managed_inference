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

# Persistent disk for model storage
resource "google_compute_disk" "model_cache" {
  name  = "atomix-model-cache"
  type  = "pd-balanced"
  zone  = var.zone
  size  = 500  # 500GB for model storage

  labels = {
    purpose = "model-cache"
  }
}

# GCP Compute Instance with 8x L4 24GB GPUs
resource "google_compute_instance" "atomix_bench" {
  name         = "atomix-bench-l4"
  machine_type = "g2-standard-96"  # 8x L4 24GB
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-cu128-ubuntu-2204-nvidia-570"
      size  = 200  # Reduced boot disk, models on separate disk
      type  = "pd-balanced"
    }
  }

  # Attach persistent disk for model storage
  attached_disk {
    source      = google_compute_disk.model_cache.id
    device_name = "model-cache"
    mode        = "READ_WRITE"
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

    # Mount persistent disk for model storage
    DEVICE="/dev/disk/by-id/google-model-cache"
    MOUNT_POINT="/mnt/model-cache"

    # Check if disk is already formatted
    if ! blkid $DEVICE; then
      echo "Formatting persistent disk..."
      mkfs.ext4 -F $DEVICE
    fi

    # Create mount point and mount
    mkdir -p $MOUNT_POINT
    if ! mountpoint -q $MOUNT_POINT; then
      echo "Mounting persistent disk..."
      mount $DEVICE $MOUNT_POINT
    fi

    # Add to fstab if not already present
    if ! grep -q "$DEVICE" /etc/fstab; then
      echo "$DEVICE $MOUNT_POINT ext4 defaults,nofail 0 2" >> /etc/fstab
    fi

    # Create HuggingFace cache directory on persistent disk
    mkdir -p $MOUNT_POINT/huggingface
    chown -R 1000:1000 $MOUNT_POINT/huggingface
    chmod -R 755 $MOUNT_POINT/huggingface

    echo "Setup complete! Ready for vLLM deployment."
    echo "Model cache mounted at: $MOUNT_POINT/huggingface"
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
