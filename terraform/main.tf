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

# GCP Compute Instance with 6x H100 80GB GPUs
resource "google_compute_instance" "modelsguard_bench" {
  name         = "modelsguard-bench-h100"
  machine_type = "a3-highgpu-8g"  # 8x H100 80GB (we'll use 6)
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 500  # 500GB boot disk
      type  = "pd-balanced"
    }
  }

  # Additional disk for models and cache
  scratch_disk {
    interface = "NVME"
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  guest_accelerator {
    type  = "nvidia-h100-80gb"
    count = 6
  }

  scheduling {
    on_host_maintenance = "TERMINATE"  # Required for GPU instances
    automatic_restart   = false
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
  }

  metadata_startup_script = file("${path.module}/startup.sh")

  tags = ["modelsguard-bench", "http-server", "https-server"]
}

# Firewall rules for vLLM endpoints
resource "google_compute_firewall" "vllm_ports" {
  name    = "modelsguard-vllm-ports"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8001-8005", "8080", "8081", "22"]
  }

  source_ranges = ["0.0.0.0/0"]  # Restrict this in production
  target_tags   = ["modelsguard-bench"]
}

output "instance_ip" {
  value       = google_compute_instance.modelsguard_bench.network_interface[0].access_config[0].nat_ip
  description = "Public IP of the benchmark instance"
}

output "instance_name" {
  value       = google_compute_instance.modelsguard_bench.name
  description = "Name of the instance"
}
