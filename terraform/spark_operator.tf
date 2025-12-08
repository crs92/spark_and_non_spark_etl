# spark_operator.tf

# 1. Define the namespace for the Spark Operator
resource "kubernetes_namespace" "spark_operator_ns" {
  metadata {
    name = "spark-operator"
  }
}

# 2. Install the Spark Operator using the official Helm repository
resource "helm_release" "spark_operator" {
  depends_on = [kubernetes_namespace.spark_operator_ns]

  name       = "spark-operator"
  repository = "https://kubeflow.github.io/spark-operator"
  chart      = "spark-operator"
  version    = "1.4.6"  # Stable version that works with Spark 3.5.0
  namespace  = kubernetes_namespace.spark_operator_ns.metadata[0].name

  # Enable webhook for SparkApplication validation
  set {
    name  = "webhook.enable"
    value = "true"
  }

  # RBAC configuration
  set {
    name  = "rbac.create"
    value = "true"
  }

  # Allow Spark jobs in default namespace
  set {
    name  = "sparkJobNamespace"
    value = "default"
  }

  # Tolerations for critical addons
  set {
    name  = "tolerations[0].key"
    value = "CriticalAddonsOnly"
  }
  set {
    name  = "tolerations[0].operator"
    value = "Exists"
  }
  set {
    name  = "webhook.tolerations[0].key"
    value = "CriticalAddonsOnly"
  }
  set {
    name  = "webhook.tolerations[0].operator"
    value = "Exists"
  }

  # Wait for the release to be ready
  wait    = true
  timeout = 300  # 5 minutes
}
