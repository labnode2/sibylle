# The realm. Its settings are those of ../dev-realm.json, the local Keycloak's ("What the realm
# sets" in ../README.md): change both together.
resource "keycloak_realm" "sibylle" {
  realm        = "sibylle"
  enabled      = true
  display_name = "Sibylle"

  login_theme = "sibylle"
  email_theme = "sibylle"

  # French only, as the app. Without it, Keycloak shows its English texts.
  internationalization {
    supported_locales = ["fr"]
    default_locale    = "fr"
  }

  registration_allowed           = true
  registration_email_as_username = true
  login_with_email_allowed       = true
  duplicate_emails_allowed       = false
  reset_password_allowed         = true
  remember_me                    = false
  # An account whose address is not confirmed yet may play (spec FR-002): no "Verify email" at
  # sign-up. The app asks Keycloak to send the address check instead.
  verify_email = false

  # The page's hint, "8 CARACTÈRES AU MOINS", is in the theme's messages_fr.properties.
  password_policy = "length(8)"

  # Links valid 1 hour when the person asks (forgotten password), 24 hours when the app does
  # (address check), as the app's own links were.
  action_token_generated_by_user_lifespan  = "1h"
  action_token_generated_by_admin_lifespan = "24h"

  security_defenses {
    # Keycloak's own defaults, written out: without them the provider would send none.
    headers {
      x_frame_options                     = "SAMEORIGIN"
      content_security_policy             = "frame-src 'self'; frame-ancestors 'self'; object-src 'none';"
      content_security_policy_report_only = ""
      x_content_type_options              = "nosniff"
      x_robots_tag                        = "none"
      x_xss_protection                    = "1; mode=block"
      strict_transport_security           = "max-age=31536000; includeSubDomains"
      referrer_policy                     = "no-referrer"
    }
    # research.md R4: 10 failed sign-ins within 15 minutes lock an account for a while, never
    # for good.
    brute_force_detection {
      permanent_lockout          = false
      max_login_failures         = 10
      wait_increment_seconds     = 60
      max_failure_wait_seconds   = 900
      failure_reset_time_seconds = 900
    }
  }

  smtp_server {
    host              = var.smtp_host
    port              = var.smtp_port
    from              = var.mail_from
    from_display_name = var.mail_from_name
    starttls          = true

    auth {
      username = var.smtp_user
      password = var.smtp_password
    }
  }
}

# The app's client. Sibylle's server signs people in itself (authorization code with PKCE) and
# keeps its own session cookie, so a browser never holds a token. The addresses below are the
# ones its server will answer on.
resource "keycloak_openid_client" "sibylle" {
  realm_id  = keycloak_realm.sibylle.id
  client_id = "sibylle"
  name      = "Sibylle"
  enabled   = true

  access_type                  = "CONFIDENTIAL"
  standard_flow_enabled        = true
  implicit_flow_enabled        = false
  direct_access_grants_enabled = false
  # Its own account, to delete a person's account and send the address check (below).
  service_accounts_enabled = true

  root_url = var.app_origin
  base_url = "/"
  # The way back from Keycloak's pages, and the end of the address check's link: a sign-in that
  # Keycloak passes at once, back to the settings (/api/auth/login?suite=/compte, research.md K9).
  valid_redirect_uris = [
    "${var.app_origin}/api/auth/callback",
    "${var.app_origin}/api/auth/login*",
  ]
  valid_post_logout_redirect_uris = ["${var.app_origin}/*"]
  web_origins                     = []
  pkce_code_challenge_method      = "S256"

  # Keycloak tells the app's server when a session ends: signed out elsewhere, a new password, an
  # administrator's « Sign out ». It calls Sibylle's nginx over the VM's network (research.md K8).
  frontchannel_logout_enabled         = false
  backchannel_logout_url              = var.backchannel_logout_url
  backchannel_logout_session_required = true
}

# The client's default scopes: those Keycloak gives a client with a service account, and
# kc-admin-api, whose audience Keycloak 26.8 wants on a token of its admin API: without it, the
# service account's calls get 401 (research.md K5).
resource "keycloak_openid_client_default_scopes" "sibylle" {
  realm_id  = keycloak_realm.sibylle.id
  client_id = keycloak_openid_client.sibylle.id
  default_scopes = [
    "web-origins",
    "service_account",
    "acr",
    "profile",
    "roles",
    "basic",
    "email",
    "kc-admin-api",
  ]
}

# The client's account manages the realm's users, and nothing else.
data "keycloak_openid_client" "realm_management" {
  realm_id  = keycloak_realm.sibylle.id
  client_id = "realm-management"
}

resource "keycloak_openid_client_service_account_role" "manage_users" {
  realm_id                = keycloak_realm.sibylle.id
  service_account_user_id = keycloak_openid_client.sibylle.service_account_user_id
  client_id               = data.keycloak_openid_client.realm_management.id
  role                    = "manage-users"
}
