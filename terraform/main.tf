terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
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
      size  = 10
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

  tags = ["kvcached", "http-server"]

  lifecycle {
    ignore_changes = [
      metadata_startup_script,
      boot_disk,
      network_interface,
      metadata,
      labels,
      service_account,
    ]
  }
}

resource "null_resource" "deploy_kvcached" {
  triggers = {
    hf_token     = var.hf_token
    instance_id  = google_compute_instance.kvcached_instance.instance_id
  }

  provisioner "remote-exec" {
    inline = [
      "set -e",
      "sudo bash -c 'exec > >(tee /var/log/kvcached-deploy.log) 2>&1'",

      # Install dependencies
      "sudo apt-get update",
      "sudo apt-get install -y curl wget git jq python3-pip",

      # Install Docker if not present
      "if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com | sudo sh; fi",

      # Install Docker Compose if not present
      "if ! command -v docker-compose &> /dev/null; then sudo curl -L 'https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose; fi",

      # Install NVIDIA Container Toolkit
      "sudo rm -f /etc/apt/sources.list.d/nvidia-container-toolkit.list",
      "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
      "curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list",
      "sudo apt-get update",
      "sudo apt-get install -y nvidia-container-toolkit",
      "sudo nvidia-ctk runtime configure --runtime=docker",
      "sudo systemctl restart docker",

      # Clone repo
      "cd /root",
      "sudo rm -rf benchmarking_managed_inference",
      "sudo git clone https://github.com/AXIONResearch/benchmarking_managed_inference.git",
      "cd benchmarking_managed_inference",
      "sudo git checkout kvcached",

      # Configure HF token
      "echo 'HF_TOKEN=${var.hf_token}' | sudo tee docker/managed/.env",

      # Copy T4 configs
      "sudo cp docker/managed/smart-lb/app.t4.py docker/managed/smart-lb/app.py",

      # Deploy
      "cd docker/managed",
      "sudo docker-compose -f docker-compose.t4.yml pull",
      "sudo docker-compose -f docker-compose.t4.yml up -d",

      # Install Python deps
      "sudo pip3 install aiohttp numpy pandas matplotlib",

      "echo 'KVCached deployment complete'",
      "sudo nvidia-smi"
    ]

    connection {
      type        = "ssh"
      host        = self.triggers.instance_id != "" ? google_compute_instance.kvcached_instance.network_interface[0].access_config[0].nat_ip : ""
      user        = "omrifainaro"
      private_key = file("~/.ssh/google_compute_engine")
    }
  }
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
