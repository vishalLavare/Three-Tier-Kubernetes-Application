# Deployment Guide: Three-Tier Kubernetes Application

This document provides step-by-step instructions for deploying the **Three-Tier Kubernetes Application** to various Kubernetes cluster environments.

---

## 1. Prerequisites

Before attempting any deployment, ensure the following local utilities are installed:

- **Docker**: Engine version 20.10+
- **kubectl**: CLI matching your Kubernetes server version.
- **Git**: For cloning and repository tracking.
- **helm** *(optional)*: For managing external charts if required.

---

## 2. Local Deployments

### Option A: Docker Desktop (Windows / macOS)

Docker Desktop provides a built-in single-node Kubernetes cluster.

1. **Enable Kubernetes**:
   - Open Docker Desktop settings.
   - Select **Kubernetes** from the sidebar.
   - Check **Enable Kubernetes** and click **Apply & restart**.

2. **Verify Context**:
   ```bash
   kubectl config use-context docker-desktop
   kubectl cluster-info
   ```

3. **Install Ingress Controller**:
   Install the official NGINX Ingress Controller:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
   ```
   *Wait for the Ingress controller pods to be fully running (`kubectl get pods -n ingress-nginx`).*

4. **Build Local Images**:
   Docker Desktop shares its Docker daemon with Kubernetes. Build the images in your local shell:
   ```bash
   # From project root
   docker build -t three-tier-backend:latest -f docker/backend.Dockerfile .
   docker build -t three-tier-frontend:latest -f docker/frontend.Dockerfile .
   ```

5. **Deploy Resources**:
   Proceed to the [Deploying Manifests](#3-deploying-manifests) section.

---

### Option B: Minikube

Minikube is a lightweight Kubernetes implementation that creates a VM or container on your local machine.

1. **Start Minikube**:
   ```bash
   minikube start --driver=docker --addons=ingress
   ```
   *This starts Minikube using Docker as the driver and automatically activates the NGINX Ingress addon.*

2. **Point CLI to Minikube's Docker Daemon**:
   To avoid pushing images to Docker Hub, point your terminal's docker CLI to Minikube's internal Docker registry:
   - **Linux/macOS**:
     ```bash
     eval $(minikube docker-env)
     ```
   - **Windows (PowerShell)**:
     ```powershell
     minikube docker-env | Invoke-Expression
     ```

3. **Build Images**:
   Build the images inside the Minikube registry context:
   ```bash
   docker build -t three-tier-backend:latest -f docker/backend.Dockerfile .
   docker build -t three-tier-frontend:latest -f docker/frontend.Dockerfile .
   ```

4. **Deploy Resources**:
   Proceed to the [Deploying Manifests](#3-deploying-manifests) section.

5. **Access Application**:
   Get the Minikube IP address for accessing the ingress:
   ```bash
   minikube ip
   ```
   Add this IP to your `/etc/hosts` file mapped to a domain (e.g. `three-tier.local`), or use `minikube tunnel` to route local port 80 to Minikube's Ingress.

---

### Option C: Kind (Kubernetes in Docker)

Kind runs local Kubernetes clusters using Docker container "nodes".

1. **Create Config File**:
   Create a file named `kind-config.yaml` to expose host ports 80 and 443 to the Ingress controller:
   ```yaml
   kind: Cluster
   apiVersion: kind.x-k8s.io/v1alpha4
   nodes:
     - role: control-plane
       kubeadmConfigPatches:
         - |
           kind: InitConfiguration
           nodeRegistration:
             kubeletExtraArgs:
               node-labels: "ingress-ready=true"
       extraPortMappings:
         - containerPort: 80
           hostPort: 80
           protocol: TCP
         - containerPort: 443
           hostPort: 443
           protocol: TCP
   ```

2. **Create Cluster**:
   ```bash
   kind create cluster --config kind-config.yaml
   ```

3. **Install Ingress Controller**:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
   ```

4. **Build and Load Images**:
   Build the images locally, then load them into the Kind cluster:
   ```bash
   # Build
   docker build -t three-tier-backend:latest -f docker/backend.Dockerfile .
   docker build -t three-tier-frontend:latest -f docker/frontend.Dockerfile .
   
   # Load
   kind load docker-image three-tier-backend:latest
   kind load docker-image three-tier-frontend:latest
   ```

5. **Deploy Resources**:
   Proceed to the [Deploying Manifests](#3-deploying-manifests) section.

---

## 3. Deploying Manifests

Deploy resources in the logical order of their dependency (Namespace -> Configs -> Volume -> Database -> Apps -> Ingress/Bonus):

1. **Create Namespace**:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```

2. **Apply Configurations and Secrets**:
   ```bash
   kubectl apply -f k8s/config/configmap.yaml
   kubectl apply -f k8s/config/secret.yaml
   ```

3. **Deploy PostgreSQL Database**:
   ```bash
   kubectl apply -f k8s/database/db-init-configmap.yaml
   kubectl apply -f k8s/database/persistent-volume.yaml
   kubectl apply -f k8s/database/persistent-volume-claim.yaml
   kubectl apply -f k8s/database/deployment.yaml
   kubectl apply -f k8s/database/service.yaml
   ```
   *Wait for PostgreSQL to be healthy (`kubectl get pods -n three-tier-app -l app=postgres -w`).*

4. **Deploy Backend (FastAPI)**:
   ```bash
   kubectl apply -f k8s/backend/deployment.yaml
   kubectl apply -f k8s/backend/service.yaml
   ```

5. **Deploy Frontend (React)**:
   ```bash
   kubectl apply -f k8s/frontend/deployment.yaml
   kubectl apply -f k8s/frontend/service.yaml
   ```

6. **Enable Ingress Routing**:
   ```bash
   kubectl apply -f k8s/ingress/ingress.yaml
   ```

7. **Deploy Bonus Operations (HPA, Network Policies, PDBs, Quotas)**:
   ```bash
   kubectl apply -f k8s/bonus/resource-quota.yaml
   kubectl apply -f k8s/bonus/hpa.yaml
   kubectl apply -f k8s/bonus/network-policy.yaml
   kubectl apply -f k8s/bonus/pdb.yaml
   ```

---

## 4. Verification and Validation

Run these commands to ensure the infrastructure has loaded successfully:

- **Check Pod Statuses**:
  ```bash
  kubectl get pods -n three-tier-app
  ```
  *Ensure all pods show `Running` and have a `2/2` or `1/1` Ready state.*

- **Check Services**:
  ```bash
  kubectl get svc -n three-tier-app
  ```

- **Check Ingress Route**:
  ```bash
  kubectl get ingress -n three-tier-app
  ```

- **Inspect DB Logs**:
  ```bash
  kubectl logs -n three-tier-app -l app=postgres
  ```

- **Inspect Backend Logs**:
  ```bash
  kubectl logs -n three-tier-app -l app=backend
  ```

---

## 5. Amazon EKS Deployment (Cloud Production)

For deployment in AWS EKS, follow these production guidelines:

1. **Provision EKS Cluster**:
   Using `eksctl`:
   ```bash
   eksctl create cluster --name three-tier-cluster --region us-east-1 --nodegroup-name standard-workers --node-type t3.medium --nodes 3
   ```

2. **Replace HostPath PV with EKS EBS CSI Driver**:
   Production databases should not use `hostPath` volumes. Instead, provision an EBS storage class using EKS EBS CSI driver:
   - Install the AWS EBS CSI driver addon.
   - Update `persistent-volume-claim.yaml` to request storage using the `gp3` storage class instead of the custom `manual` StorageClass.
   - Remove `persistent-volume.yaml` from your manifest run (as EKS will dynamically provision the AWS EBS volume on-demand!).

3. **Install AWS Load Balancer Controller**:
   The NGINX Ingress controller in EKS will provision an AWS Network Load Balancer (NLB) or Classic Load Balancer (CLB) automatically to handle public traffic routing.
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx \
     --namespace ingress-nginx \
     --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="external" \
     --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-nlb-target-type"="instance" \
     --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-scheme"="internet-facing"
   ```

4. **Tag Images & Push to AWS ECR**:
   ```bash
   # Create ECR Repositories
   aws ecr create-repository --repository-name three-tier-backend
   aws ecr create-repository --repository-name three-tier-frontend
   
   # Login and push
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   
   docker tag three-tier-backend:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/three-tier-backend:latest
   docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/three-tier-backend:latest
   
   # Repeat for frontend...
   ```

5. **Update Manifest Image Tags**:
   Update `image:` fields in `backend/deployment.yaml` and `frontend/deployment.yaml` to point to ECR paths before applying.
