#!/bin/bash
# ACMS Deployment Script
# Version: 1.0.0
# Date: 2025-11-02
# Owner: Platform.Engineering
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 [-e environment] [-s stack]

Options:
  -e ENVIRONMENT   Deployment environment (dev, staging, prod). Defaults to dev.
  -s STACK         Pulumi stack name. Defaults to acms-infrastructure.
  -h               Show this help message.

The script performs a deterministic Pulumi deployment:
  1. Validates prerequisites (pulumi CLI).
  2. Configures the environment specific settings.
  3. Executes \`pulumi up\` in non-interactive mode.
  4. Records the deployment summary to logs/deployments.jsonl.
USAGE
}

log_dir="logs"
mkdir -p "$log_dir"
ledger="$log_dir/deployments.jsonl"

environment="dev"
stack="acms-infrastructure"

while getopts ":e:s:h" opt; do
  case "$opt" in
    e)
      environment="$OPTARG"
      ;;
    s)
      stack="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    :)
      echo "Error: Option -$OPTARG requires an argument" >&2
      exit 1
      ;;
    \?)
      echo "Error: Invalid option -$OPTARG" >&2
      usage
      exit 1
      ;;
  esac
done

command -v pulumi >/dev/null 2>&1 || { echo "pulumi CLI not found" >&2; exit 127; }

pushd infrastructure/pulumi >/dev/null
pulumi stack select "$stack" --create
pulumi config set environment "$environment" --stack "$stack" --non-interactive

pulumi up --yes --stack "$stack" --non-interactive

pulumi stack output --stack "$stack" --json > ../../logs/last_deployment.json
popd >/dev/null

printf '{"timestamp": "%s", "environment": "%s", "stack": "%s"}\n' \
  "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  "$environment" \
  "$stack" >> "$ledger"
