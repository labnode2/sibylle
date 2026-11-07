# Sibylle's realm in production's Keycloak (README.md next to this file), run through tofu.sh.
terraform {
  required_version = "~> 1.13"

  required_providers {
    keycloak = {
      source  = "keycloak/keycloak"
      version = "~> 5.10"
    }
  }
}

# The master realm's `terraform` client, through the SSH tunnel: tofu.sh passes KEYCLOAK_URL,
# KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET from the environment.
provider "keycloak" {
  realm = "master"
}
