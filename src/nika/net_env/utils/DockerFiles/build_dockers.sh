#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build Docker images for all services
docker build -f "$BASE_DIR/Dockerfile.frr" -t kathara/nika-frr "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.base" -t kathara/nika-base "$BASE_DIR"
# docker build -f "$BASE_DIR/Dockerfile.ryu" -t kathara/nika-ryu "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.nginx" -t kathara/nika-nginx "$BASE_DIR"
docker build -f "$BASE_DIR/Dockerfile.wireguard" -t kathara/nika-wireguard "$BASE_DIR"
