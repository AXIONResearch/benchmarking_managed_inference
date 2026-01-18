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

# GCP Compute Instance for KVCached benchmarking
resource "google_compute_instance" "modelsguard_bench" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10  # Match existing boot disk size
      type  = "pd-balanced"
    }
  }

  # Note: Scratch disk commented out as it doesn't exist on current VM
  # Uncomment if creating new VM with scratch disk for model cache
  # scratch_disk {
  #   interface = "NVME"
  # }

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
    on_host_maintenance = "TERMINATE"  # Required for GPU instances
    automatic_restart   = false
  }

  metadata_startup_script = file("${path.module}/startup.sh")

  # Tags commented out to match existing VM - add tags only when needed
  # tags = ["modelsguard-bench", "http-server", "https-server"]

  # Lifecycle configuration to prevent accidental changes to existing VM
  lifecycle {
    ignore_changes = [
      metadata,
      metadata_startup_script,
      service_account,
      labels,
      boot_disk,
      network_interface,
    ]
  }
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
