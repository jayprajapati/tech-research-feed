targetScope = 'resourceGroup'

param location string = resourceGroup().location

var suffix = uniqueString(resourceGroup().id)

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${suffix}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2' }
}

resource reportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storage.name}/default/reports'
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01' = {
  name: 'cr${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: true }
}

output resourceGroupName string = resourceGroup().name
output storageAccountName string = storage.name
output containerRegistryName string = containerRegistry.name
