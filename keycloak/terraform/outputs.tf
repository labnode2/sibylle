output "issuer" {
  description = "The realm's issuer, for the app's settings."
  value       = "${var.keycloak_public_url}/realms/${keycloak_realm.sibylle.realm}"
}

output "client_id" {
  description = "The app's client, for its settings."
  value       = keycloak_openid_client.sibylle.client_id
}

output "client_secret" {
  description = "The app's client secret, for deploy/.env: tofu.sh output -raw client_secret."
  value       = keycloak_openid_client.sibylle.client_secret
  sensitive   = true
}
