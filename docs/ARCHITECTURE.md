# Architecture & Concepts

## Tiers
1. **Presentation** – nginx on `frontend-vmss` serves static HTML/JS and reverse-proxies `/api/*` to the internal LB (`10.20.2.10:5000`). Browsers never talk to Storage or to the backend directly.
2. **Application** – Flask/gunicorn on `backend-vmss`; only tier with an identity and a route to Storage.
3. **Storage** – one Storage Account, private endpoint only.

## Managed Identity & Entra ID
- **Why identities?** Resources must prove *who* they are so access can be granted, limited, audited and revoked. Shared keys prove nothing about the caller and grant everything.
- **Service principal** – the identity object of an app in Microsoft Entra ID (like a user account for software). It holds credentials (secret/cert) in the classic model.
- **Managed Identity** – a service principal whose credentials Azure creates, stores and rotates for you; the app just asks IMDS for a token. **System-assigned**: tied to one resource's lifecycle (deleted with it; one per VMSS, shared by all its instances). **User-assigned**: standalone resource you attach to many resources, survives deletion, pre-grant RBAC before deploying.
- **vs traditional service account** – a service account is a username+password you create, store, rotate and can leak; a managed identity has no secret you can see.
- **Why avoid account keys** – full-power, un-attributable, never expire unless rotated, leak via git/logs. Here `allowSharedKeyAccess=false` makes keys unusable.
- **Token flow** – app → IMDS (link-local, only reachable from the VM) → Entra ID issues a JWT (audience `https://storage.azure.com`, `oid` = principal ID, ~24 h, cached/refreshed by the SDK) → Storage validates signature/audience.
- **RBAC** – authentication says *who*; RBAC says *what*: role (`Storage Blob Data Contributor` = read/write/delete blobs + containers) + scope (storage account) + principal. Control-plane "Owner/Contributor" does **not** grant data access — data roles are separate.

## Networking
- **VNet** – private isolated network (`10.20.0.0/16`). **Subnet** – slice of it; policies (NSG, NAT, routes) attach per subnet.
- **NSG** – stateful allow/deny rules by priority (lowest first), inbound & outbound, 5-tuple + service tags. **ASG** – a label for NICs so rules say "from asg-frontend to asg-backend" instead of IPs. NSG = the rule set; ASG = a named group used inside rules. Autoscaled VMs join the ASG automatically.
- **Traffic flow** – Internet → public LB → NIC (nsg-frontend allows 80) → nginx → internal LB → NIC (nsg-backend allows 5000 *only* from asg-frontend) → Flask → private endpoint 443 → Storage.
- **Why frontend can't reach Blob** – it has no identity, no RBAC, and the browser never receives credentials; Storage has no public endpoint.
- **Private endpoint + DNS** – the PE puts a NIC with a private IP in `private-endpoint-subnet`. Private DNS zone `privatelink.blob.core.windows.net` (linked to the VNet) makes `<acct>.blob.core.windows.net` resolve to that IP; without the link it resolves to the public IP, which is blocked.
- **When an NSG blocks API traffic** – nginx gets timeouts → HTTP 502/504 to the browser; backend logs show nothing.

## VM Scale Sets
A VM is one machine; a VMSS is a managed group of identical VMs from one model (image + cloud-init + NIC/ASG + identity). Autoscale reads `Percentage CPU`; when the rule fires Azure creates/deletes instances; the LB health probe adds an instance only after it answers, so the app stays available. All backend instances share **one** system-assigned identity → one RBAC assignment covers every instance, all writing the same storage account. State lives in Blob (not on VMs), so instances are disposable. ETags protect against two instances editing the same blob.

## Design decisions
Individual blob per entity (no shared JSON → no lost updates, simple CRUD); unique audit filenames (no append conflicts); LB probe is shallow so a Storage outage doesn't make autoscaling flap; NAT Gateway gives VMs outbound for `apt/pip` only.
