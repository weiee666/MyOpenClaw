# OpenClaw User Pod Service

This folder contains an independent frontend and backend for creating isolated OpenClaw pods per user.

## Structure

- `User/frontend`: React UI for launching pods
- `User/backend`: Node API that creates Kubernetes resources
- `User/backend/k8s`: RBAC + deployment manifests for the backend

## Backend environment

- `PORT`: API port (default 4000)
- `OPENCLAW_IMAGE`: OpenClaw image to deploy
- `OPENCLAW_STORAGE_CLASS`: Optional storage class for PVCs
- `OPENCLAW_INGRESS_CLASS`: Optional ingress class name

## Frontend environment

- `VITE_API_BASE`: API base URL (default empty for same-origin)
