targetScope = 'resourceGroup'

param location string = resourceGroup().location
param storageSku string = 'Standard_LRS'
param containerImageName string = 'trader-agent:latest'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: storageSku }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
  }
}

resource reportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storage.name}/default/reports'
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01' = {
  name: 'cr${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: true }
}

resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: 'swa-trader-news'
  location: location
  sku: { name: 'Standard' }
  properties: {
    repositoryUrl: ''
    branch: 'main'
    buildProperties: { appLocation: 'website', outputLocation: 'dist' }
  }
}
