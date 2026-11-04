// RBAC: backend VMSS system-assigned identity -> Storage Blob Data Contributor on the storage account
param principalId string
param storageName string

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' existing = { name: storageName }

var blobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sa
  name: guid(sa.id, principalId, blobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributor)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
