#!/usr/bin/env bash
set -euo pipefail

# Simple helper script to:
# 1. Install Ansible and deps on Ubuntu
# 2. Install Ansible collections
# 3. Run the playbook against the local machine

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for nicer output
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
}

ensure_sudo() {
  if [ "$EUID" -ne 0 ]; then
    if require_cmd sudo; then
      sudo -v
    else
      log_error "sudo is not available but required. Install sudo or run as root."
      exit 1
    fi
  fi
}

install_ansible_and_deps() {
  if require_cmd ansible && require_cmd ansible-playbook; then
    log_info "Ansible already installed. Skipping Ansible install."
    return
  fi

  log_info "Installing Ansible and dependencies on Ubuntu."

  ensure_sudo

  sudo apt update -y
  sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    software-properties-common

  # Use distro Ansible
  sudo apt install -y ansible

  log_info "Ansible installation completed."
}

install_collections() {
  if [ -f "${REPO_ROOT}/requirements.yml" ]; then
    log_info "Installing Ansible collections from requirements.yml."
    ansible-galaxy collection install -r "${REPO_ROOT}/requirements.yml"
  else
    log_warn "No requirements.yml found. Installing kubernetes.core directly."
    ansible-galaxy collection install kubernetes.core
  fi
}

check_ansible_files() {
  if [ ! -f "${REPO_ROOT}/site.yml" ]; then
    log_error "site.yml not found in repo root (${REPO_ROOT})."
    exit 1
  fi

  if [ ! -f "${REPO_ROOT}/inventory.ini" ]; then
    log_error "inventory.ini not found in repo root (${REPO_ROOT})."
    exit 1
  fi
}

run_playbook() {
  log_info "Running Ansible playbook."

  # If you are running on the same VM, inventory.ini should contain localhost
  # with ansible_connection=local
  ansible-playbook -i "${REPO_ROOT}/inventory.ini" "${REPO_ROOT}/site.yml"
}

main() {
  log_info "Starting k3s lab setup from repo: ${REPO_ROOT}"

  install_ansible_and_deps
  install_collections
  check_ansible_files
  run_playbook

  log_info "All done. You can now use kubectl to inspect the cluster."
  log_info "Examples:"
  echo "  kubectl get nodes -o wide"
  echo "  kubectl get pods -A"
}

main "$@"
