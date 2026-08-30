// City Hospital — Azure infrastructure for the AKS deployment.
//
//   az deployment group create -g <rg> -f deploy/azure/main.bicep \
//      -p namePrefix=cityhosp postgresAdminPassword='<strong>'
//
// Provisions: Container Registry, AKS (with OIDC + workload identity), Azure
// Cache for Redis, PostgreSQL Flexible Server, Key Vault, a user-assigned
// managed identity federated to the cluster's service account, and Log
// Analytics.
//
// Redis and PostgreSQL are managed services rather than in-cluster
// StatefulSets on purpose. Redis holds the connection routing that lets any
// pod reach any customer's socket, and PostgreSQL holds clinical records —
// neither is something to run single-replica on a node that can be drained.

targetScope = 'resourceGroup'

@description('Prefix for every resource name. Lowercase letters and digits.')
@minLength(3)
@maxLength(12)
param namePrefix string

@description('Region for all resources.')
param location string = resourceGroup().location

@description('Kubernetes namespace and service account the workload identity is federated to.')
param k8sNamespace string = 'cityhospital'
param k8sServiceAccount string = 'cityhospital'

@description('Node count for the system pool.')
@minValue(1)
param nodeCount int = 2

@description('VM size for the system pool.')
param nodeVmSize string = 'Standard_D2s_v5'

@description('Administrator login for PostgreSQL.')
param postgresAdminUser string = 'cityhospital'

@description('Administrator password for PostgreSQL.')
@secure()
param postgresAdminPassword string

@description('Name of the application database.')
param postgresDatabaseName string = 'cityhospital'

var suffix = uniqueString(resourceGroup().id)
var acrName = toLower('${namePrefix}acr${suffix}')
var aksName = '${namePrefix}-aks'
var redisName = '${namePrefix}-redis-${suffix}'
var pgName = '${namePrefix}-pg-${suffix}'
var kvName = take(toLower('${namePrefix}kv${suffix}'), 24)
var identityName = '${namePrefix}-workload-id'
var logsName = '${namePrefix}-logs'

// --------------------------------------------------------------------------- //
// Observability
// --------------------------------------------------------------------------- //
resource logs 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// --------------------------------------------------------------------------- //
// Container registry
// --------------------------------------------------------------------------- //
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    // The cluster pulls with its managed identity, so there is no admin
    // credential to leak or rotate.
    adminUserEnabled: false
  }
}

// --------------------------------------------------------------------------- //
// Kubernetes
// --------------------------------------------------------------------------- //
resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: aksName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: aksName
    // Both are required for workload identity: the OIDC issuer publishes the
    // keys that let Entra ID trust the cluster's service account tokens.
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        osSKU: 'AzureLinux'
        type: 'VirtualMachineScaleSets'
        enableAutoScaling: true
        minCount: nodeCount
        maxCount: 6
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'cilium'
      networkDataplane: 'cilium'
      loadBalancerSku: 'standard'
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logs.id
        }
      }
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: {
          enableSecretRotation: 'true'
        }
      }
    }
    // The managed ingress-nginx add-on. The AKS overlay's ingress uses its
    // class: webapprouting.kubernetes.azure.com
    ingressProfile: {
      webAppRouting: {
        enabled: true
      }
    }
  }
}

// Let the cluster's kubelet identity pull from the registry. Without this the
// pods sit in ImagePullBackOff with no obvious cause.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, aks.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: aks.properties.identityProfile.kubeletidentity.objectId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// --------------------------------------------------------------------------- //
// Workload identity for the application pods
// --------------------------------------------------------------------------- //
resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

// Federates the Kubernetes service account to the managed identity: a pod
// using that service account gets an Entra token without any stored secret.
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: workloadIdentity
  name: 'aks-${k8sNamespace}-${k8sServiceAccount}'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:${k8sNamespace}:${k8sServiceAccount}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

// --------------------------------------------------------------------------- //
// Secrets
// --------------------------------------------------------------------------- //
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    // RBAC rather than access policies, so the workload identity below is
    // granted through a role assignment like everything else.
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource kvRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workloadIdentity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: workloadIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalType: 'ServicePrincipal'
  }
}

// --------------------------------------------------------------------------- //
// Redis — connection routing, sessions, idempotency, the event bus
// --------------------------------------------------------------------------- //
resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  properties: {
    sku: {
      // Basic has no SLA and no replica. Standard is the floor for something
      // that, if it disappears, costs every guest their resolved identity.
      name: 'Standard'
      family: 'C'
      capacity: 1
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      // Never evict: the event stream and the idempotency keys are correctness
      // state, not a cache. Silently dropping them would double-book.
      'maxmemory-policy': 'noeviction'
    }
  }
}

// --------------------------------------------------------------------------- //
// PostgreSQL — durable conversation, appointment and audit state
// --------------------------------------------------------------------------- //
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminUser
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      // Burstable does not support HA. Move to GeneralPurpose and set this to
      // ZoneRedundant before this holds real patient data.
      mode: 'Disabled'
    }
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Public access limited to Azure services. This is the pragmatic default for a
// starter environment; the production answer is VNet integration with a
// private endpoint and no public access at all.
resource postgresFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// --------------------------------------------------------------------------- //
// Outputs — feed these into the Kubernetes overlay / Secret
// --------------------------------------------------------------------------- //
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output aksName string = aks.name
output aksOidcIssuer string = aks.properties.oidcIssuerProfile.issuerURL
output keyVaultName string = keyVault.name
output workloadIdentityClientId string = workloadIdentity.properties.clientId
output redisHostName string = redis.properties.hostName
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName

@description('DATABASE_URL, minus the password — fill it in when creating the Secret.')
output databaseUrlTemplate string = 'postgresql+psycopg://${postgresAdminUser}:<password>@${postgres.properties.fullyQualifiedDomainName}:5432/${postgresDatabaseName}?sslmode=require'

@description('REDIS_URL, minus the access key. Note rediss:// and port 6380 — the non-TLS port is disabled.')
output redisUrlTemplate string = 'rediss://:<access-key>@${redis.properties.hostName}:6380/0'
