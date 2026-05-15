#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build Docker images for all services
docker build -f "$BASE_DIR/Dockerfile.frr" -t kathara/frr-stress "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.base" -t kathara/base-stress "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.ryu" -t kathara/ryu-stress "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.nginx" -t kathara/nginx-stress "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.wireguard" -t kathara/wireguard "$BASE_DIR"
