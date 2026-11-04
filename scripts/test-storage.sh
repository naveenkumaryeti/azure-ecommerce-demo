#!/usr/bin/env bash
# Acceptance tests + failure scenarios.
# ./test-storage.sh accept | nsg-block | nsg-unblock | dns-break | dns-fix | public-access
set -u; source "$(dirname "$0")/env.sh"
BASE="http://$(fe_ip)"; PASS=0; FAIL=0; ZONE="privatelink.blob.core.windows.net"
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
chk() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
jq_() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
blobs() { curl -fsS "$BASE/api/storage/containers/$1/blobs" | jq_ "' '.join(b['name'] for b in d)"; }

accept() {
  echo "== Acceptance tests against $BASE"
  chk "1  frontend loads" "curl -fsS $BASE/ | grep -q AzureKart"
  chk "   backend health through NSG/ASG path" "curl -fsS $BASE/api/health"
  R=$(curl -fsS -X POST "$BASE/api/products" -H 'Content-Type: application/json' -d '{"name":"Test Laptop","category":"Electronics","price":55000,"quantity":10,"description":"acceptance test"}')
  ID=$(echo "$R" | jq_ "d['id']"); ETAG=$(echo "$R" | jq_ "d['etag']")
  chk "2  product created via API ($ID)" "[ -n '$ID' ]"
  chk "3  JSON blob exists in products/" "blobs products | grep -q $ID.json"
  echo iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg== | base64 -d > t.png; sed -i "s#t.png#t.png#g" /dev/null
  chk "4  image uploaded to product-images/" "curl -fsS -X POST $BASE/api/products/$ID/image -F 'image=@t.png;type=image/png' && blobs product-images | grep -q $ID"
  chk "5  update changes the blob" "curl -fsS -X PUT $BASE/api/products/$ID -H 'Content-Type: application/json' -d '{\"name\":\"Test Laptop\",\"price\":49999,\"quantity\":9}' | grep -q 49999 && curl -fsS $BASE/api/products/$ID | grep -q 49999"
  chk "7  order stored as JSON blob" "curl -fsS -X POST $BASE/api/orders -H 'Content-Type: application/json' -d '{\"items\":[{\"id\":\"$ID\",\"quantity\":1}],\"customer\":{\"name\":\"Test\",\"email\":\"t@x.com\",\"address\":\"Hyderabad\"}}' && [ -n \"\$(blobs orders)\" ]"
  chk "8  audit events stored" "[ -n \"\$(blobs audit-logs)\" ]"
  chk "9  backend token via Managed Identity" "curl -fsS $BASE/api/storage/info | grep -q '\"ok\":true'"
  chk "15 dashboard shows real storage data" "curl -fsS $BASE/api/storage/info | grep -q $STORAGE_NAME"
  chk "6  delete removes the blob" "curl -fsS -X DELETE $BASE/api/products/$ID && ! blobs products | grep -q $ID.json"
  chk "10 shared-key access disabled (no keys usable)" "[ \"\$(az storage account show -g $RG -n $STORAGE_NAME --query allowSharedKeyAccess -o tsv)\" = false ]"
  chk "11 RBAC role assigned to backend identity" "$ROOT/scripts/configure-rbac.sh show | grep -q 'Storage Blob Data Contributor'"
  chk "12 NSG uses ASGs for 5000 rule" "az network nsg rule show -g $RG --nsg-name nsg-backend -n Allow-API-From-Frontend --query 'sourceApplicationSecurityGroups[0].id' -o tsv | grep -q asg-frontend"
  chk "13 private endpoint present, public access off" "[ \"\$(az storage account show -g $RG -n $STORAGE_NAME --query publicNetworkAccess -o tsv)\" = Disabled ] && az network private-endpoint list -g $RG --query '[0].name' -o tsv | grep -q blob-pe"
  chk "14 autoscale settings (1/2/4) exist" "az monitor autoscale list -g $RG --query '[].profiles[0].capacity.maximum' -o tsv | grep -q 4"
  rm -f t.png
  echo "== PASS=$PASS FAIL=$FAIL"; [ $FAIL -eq 0 ]
}

case "${1:-accept}" in
  accept) accept ;;
  nsg-block)   az network nsg rule create -g "$RG" --nsg-name nsg-backend -n Deny-Frontend-Test --priority 90 --access Deny --protocol Tcp --direction Inbound \
                 --source-asgs asg-frontend --destination-asgs asg-backend --destination-port-ranges 5000 -o table
               echo "Wait ~30s, then: curl -i $BASE/api/products  -> 504/502 from nginx (backend unreachable)" ;;
  nsg-unblock) az network nsg rule delete -g "$RG" --nsg-name nsg-backend -n Deny-Frontend-Test && echo "Rule removed; traffic restored." ;;
  dns-break)   az network private-dns link vnet delete -g "$RG" -z "$ZONE" -n vnet-link -y
               echo "VNet no longer resolves the private IP -> public IP (blocked). Wait ~1 min: curl $BASE/api/products -> 403/503" ;;
  dns-fix)     az network private-dns link vnet create -g "$RG" -z "$ZONE" -n vnet-link -v "$VNET" -e false -o table && echo "DNS link restored." ;;
  public-access) az storage account show -g "$RG" -n "$STORAGE_NAME" --query "{publicNetworkAccess:publicNetworkAccess,sharedKey:allowSharedKeyAccess}" -o table
               echo "--- from this machine (public internet) -> must fail:"
               curl -sS -o /dev/null -w "HTTP %{http_code}\n" "https://$STORAGE_NAME.blob.core.windows.net/products?restype=container&comp=list" || true
               echo "--- through the backend (private endpoint) -> must work:"; curl -fsS "$BASE/api/health?deep=1" ;;
  *) echo "usage: $0 accept|nsg-block|nsg-unblock|dns-break|dns-fix|public-access"; exit 1 ;;
esac