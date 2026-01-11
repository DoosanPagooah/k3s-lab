#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="k3s-lab"

echo "Creating project structure in $ROOT_DIR ..."

mkdir -p $ROOT_DIR
cd $ROOT_DIR

# Top level files
touch inventory.ini
touch site.yml
touch requirements.yml
touch run.sh

# Roles and subfolders
mkdir -p roles/common/tasks
mkdir -p roles/k3d_cluster/tasks
mkdir -p roles/nginx_services/tasks
mkdir -p roles/nginx_services/templates
mkdir -p roles/argocd/tasks
mkdir -p roles/monitoring/tasks

# Add placeholders so git keeps empty dirs
echo "# common role tasks" > roles/common/tasks/main.yml
echo "# k3d cluster role tasks" > roles/k3d_cluster/tasks/main.yml
echo "# nginx services role tasks" > roles/nginx_services/tasks/main.yml
echo "# nginx deployment template" > roles/nginx_services/templates/nginx-deploy.yaml.j2
echo "# argocd role tasks" > roles/argocd/tasks/main.yml
echo "# monitoring role tasks" > roles/monitoring/tasks/main.yml

# Initial inventory
cat <<'EOF' > inventory.ini
[cluster_host]
localhost ansible_connection=local
EOF

# Initial site.yml
cat <<'EOF' > site.yml
- hosts: cluster_host
  become: true

  roles:
    - common
    - k3d_cluster
    - nginx_services
    - argocd
    - monitoring
EOF

# Requirements
cat <<'EOF' > requirements.yml
collections:
  - name: kubernetes.core
EOF

# Basic run script placeholder
cat <<'EOF' > run.sh
#!/usr/bin/env bash
set -euo pipefail

ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory.ini site.yml
EOF

chmod +x run.sh

echo "Done."
echo "Project created under $(pwd)"
