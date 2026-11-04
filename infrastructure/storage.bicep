// Storage account (no keys, no public access) + containers + private endpoint + private DNS
param location string
param storageName string
param peSubnetId string
param vnetId string
param containers array = [ 'products', 'product-images', 'orders', 'audit-logs', 'application-backups' ]

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false      // account keys disabled: Entra ID + RBAC only
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'  // reachable only through the private endpoint
    networkAcls: { defaultAction: 'Deny', bypass: 'None' }
  }
}
resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: sa
  name: 'default'
  properties: { deleteRetentionPolicy: { enabled: true, days: 7 } }
}
resource cs 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for c in containers: {
  parent: blobSvc
  name: c
  properties: { publicAccess: 'None' }
}]

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${storageName}-blob-pe'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [ { name: 'blob', properties: { privateLinkServiceId: sa.id, groupIds: [ 'blob' ] } } ]
  }
}
resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
}
resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zone
  name: 'vnet-link'
  location: 'global'
  properties: { virtualNetwork: { id: vnetId }, registrationEnabled: false }
}
resource zg 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-09-01' = {
  parent: pe
  name: 'default'
  properties: { privateDnsZoneConfigs: [ { name: 'blob', properties: { privateDnsZoneId: zone.id } } ] }
}

output storageId string = sa.id
output blobEndpoint string = sa.properties.primaryEndpoints.blob
