# Cloud Run services

locals {
  database_url = "postgresql://${google_sql_user.main.name}:${random_password.db_password.result}@${google_sql_database_instance.main.private_ip_address}:5432/${google_sql_database.main.name}"
  redis_url    = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}"
  
  common_env_vars = [
    {
      name  = "DATABASE_URL"
      value = local.database_url
    },
    {
      name  = "REDIS_URL"
      value = local.redis_url
    },
    {
      name  = "LOG_LEVEL"
      value = "INFO"
    },
    {
      name  = "DEBUG"
      value = "false"
    }
  ]
}

# Gateway API
resource "google_cloud_run_v2_service" "gateway_api" {
  name     = "gateway-api"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email
    
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${output.artifact_registry_url.value}/gateway-api:latest"
      
      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.common_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "INGEST_SERVICE_URL"
        value = "https://ingest-svc-${random_id.suffix.hex}-uc.a.run.app"
      }

      env {
        name  = "EMBED_SERVICE_URL"
        value = "https://embed-svc-${random_id.suffix.hex}-uc.a.run.app"
      }

      env {
        name  = "RETRIEVAL_SERVICE_URL"
        value = "https://retrieval-svc-${random_id.suffix.hex}-uc.a.run.app"
      }

      env {
        name  = "EDITOR_SERVICE_URL"
        value = "https://editor-svc-${random_id.suffix.hex}-uc.a.run.app"
      }

      env {
        name  = "REDDIT_SYNC_SERVICE_URL"
        value = "https://reddit-sync-svc-${random_id.suffix.hex}-uc.a.run.app"
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Ingest Service
resource "google_cloud_run_v2_service" "ingest_svc" {
  name     = "ingest-svc"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email
    
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${output.artifact_registry_url.value}/ingest-svc:latest"
      
      ports {
        container_port = 8005
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.common_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Embed Service
resource "google_cloud_run_v2_service" "embed_svc" {
  name     = "embed-svc"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email
    
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${output.artifact_registry_url.value}/embed-svc:latest"
      
      ports {
        container_port = 8001
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      dynamic "env" {
        for_each = local.common_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "OPENAI_API_KEY"
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Retrieval Service
resource "google_cloud_run_v2_service" "retrieval_svc" {
  name     = "retrieval-svc"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email
    
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${output.artifact_registry_url.value}/retrieval-svc:latest"
      
      ports {
        container_port = 8002
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.common_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name  = "EMBED_SERVICE_URL"
        value = "https://embed-svc-${random_id.suffix.hex}-uc.a.run.app"
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Editor Service
resource "google_cloud_run_v2_service" "editor_svc" {
  name     = "editor-svc"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = "${output.artifact_registry_url.value}/editor-svc:latest"
      
      ports {
        container_port = 8003
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "REDIS_URL"
        value = local.redis_url
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "ANTHROPIC_API_KEY"
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Reddit Sync Service
resource "google_cloud_run_v2_service" "reddit_sync_svc" {
  name     = "reddit-sync-svc"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email
    
    vpc_access {
      connector = google_vpc_access_connector.main.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${output.artifact_registry_url.value}/reddit-sync-svc:latest"
      
      ports {
        container_port = 8004
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      dynamic "env" {
        for_each = local.common_env_vars
        content {
          name  = env.value.name
          value = env.value.value
        }
      }

      env {
        name = "REDDIT_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = "REDDIT_CLIENT_ID"
            version = "latest"
          }
        }
      }

      env {
        name = "REDDIT_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = "REDDIT_CLIENT_SECRET"
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Frontend services
resource "google_cloud_run_v2_service" "editor_frontend" {
  name     = "editor-frontend"
  location = var.region

  template {
    containers {
      image = "${output.artifact_registry_url.value}/editor-frontend:latest"
      
      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://gateway-api-${random_id.suffix.hex}-uc.a.run.app"
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

resource "google_cloud_run_v2_service" "ideahunter_frontend" {
  name     = "ideahunter-frontend"
  location = var.region

  template {
    containers {
      image = "${output.artifact_registry_url.value}/ideahunter-frontend:latest"
      
      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://gateway-api-${random_id.suffix.hex}-uc.a.run.app"
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

# Random suffix for unique service names
resource "random_id" "suffix" {
  byte_length = 4
}

# IAM for public access to frontend services
resource "google_cloud_run_service_iam_member" "editor_frontend_public" {
  location = google_cloud_run_v2_service.editor_frontend.location
  service  = google_cloud_run_v2_service.editor_frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "ideahunter_frontend_public" {
  location = google_cloud_run_v2_service.ideahunter_frontend.location
  service  = google_cloud_run_v2_service.ideahunter_frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "gateway_api_public" {
  location = google_cloud_run_v2_service.gateway_api.location
  service  = google_cloud_run_v2_service.gateway_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Service URLs outputs
output "editor_frontend_url" {
  value = google_cloud_run_v2_service.editor_frontend.uri
}

output "ideahunter_frontend_url" {
  value = google_cloud_run_v2_service.ideahunter_frontend.uri
}

output "gateway_api_url" {
  value = google_cloud_run_v2_service.gateway_api.uri
}
