# k8s_rbac.tf
# Manages service accounts and RBAC for Spark and Polars workloads
# This ensures these resources are always created after terraform apply

# Service Account for Spark workloads
resource "kubernetes_service_account" "spark_sa" {
  metadata {
    name      = "spark-sa"
    namespace = "default"
    labels = {
      app        = "spark-etl"
      managed-by = "terraform"
    }
  }

  depends_on = [module.eks]
}

# Service Account for Polars workloads
resource "kubernetes_service_account" "polars_sa" {
  metadata {
    name      = "polars-sa"
    namespace = "default"
    labels = {
      app        = "polars-etl"
      managed-by = "terraform"
    }
  }

  depends_on = [module.eks]
}

# RBAC Role for Spark driver to manage pods, services, configmaps
resource "kubernetes_role" "spark_role" {
  metadata {
    name      = "spark-role"
    namespace = "default"
  }

  # Permissions for managing pods
  rule {
    api_groups = [""]
    resources  = ["pods", "services", "configmaps"]
    verbs      = ["create", "get", "list", "watch", "delete", "patch", "update", "deletecollection"]
  }

  # Permissions for viewing pod logs
  rule {
    api_groups = [""]
    resources  = ["pods/log"]
    verbs      = ["get", "list"]
  }

  # Permissions for persistent volume claims
  rule {
    api_groups = [""]
    resources  = ["persistentvolumeclaims"]
    verbs      = ["create", "get", "list", "watch", "delete", "deletecollection"]
  }

  depends_on = [module.eks]
}

# RoleBinding to attach spark-role to spark-sa
resource "kubernetes_role_binding" "spark_role_binding" {
  metadata {
    name      = "spark-role-binding"
    namespace = "default"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role.spark_role.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.spark_sa.metadata[0].name
    namespace = "default"
  }

  depends_on = [module.eks]
}
