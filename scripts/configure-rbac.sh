#!/usr/bin/env bash
# RBAC demo helper.  ./configure-rbac.sh show|add|remove
set -euo pipefail; source "$(dirname "$0")/env.sh"
ROLE="Storage Blob Data Contributor"
PID=$(az vmss show -g "$RG" -n "$BACKEND_VMSS" --query identity.principalId -o tsv)   # identity's principal ID
SCOPE=$(az storage account show -g "$RG" -n "$STORAGE_NAME" --query id -o tsv)
echo "principalId=$PID"; echo "scope=$SCOPE"
case "${1:-show}" in
  show)   az role assignment list --assignee "$PID" --scope "$SCOPE" --query "[].{role:roleDefinitionName,scope:scope}" -o table ;;
  add)    az role assignment create --assignee-object-id "$PID" --assignee-principal-type ServicePrincipal --role "$ROLE" --scope "$SCOPE" -o table
          echo "RBAC can take up to ~5 min to propagate." ;;
  remove) az role assignment delete --assignee "$PID" --role "$ROLE" --scope "$SCOPE"
          echo "Removed. API calls now fail with AUTHORIZATION_FAILED (HTTP 403) after propagation (1-5 min)." ;;
  *) echo "usage: $0 show|add|remove"; exit 1 ;;
esac
