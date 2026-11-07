variable "app_origin" {
  description = "Where Sibylle answers: the client's sign-in and logout addresses hang off it."
  type        = string
  default     = "https://sibylle.cc"
}

variable "backchannel_logout_url" {
  description = "Where Keycloak tells Sibylle of ended sessions: its nginx, over the VM's proxy network, without Cloudflare (research.md K8)."
  type        = string
  default     = "http://sibylle:8443/api/auth/backchannel-logout"
}

variable "keycloak_public_url" {
  description = "Keycloak's public address, KC_HOSTNAME in labnode2/docker's compose file."
  type        = string
  default     = "https://auth.sibylle.cc"
}

variable "smtp_host" {
  description = "Brevo's SMTP relay, as SMTP_HOST in deploy/.env."
  type        = string
  default     = "smtp-relay.brevo.com"
}

variable "smtp_port" {
  description = "As SMTP_PORT in deploy/.env."
  type        = string
  default     = "587"
}

variable "smtp_user" {
  description = "Brevo's SMTP login, as SMTP_USER in deploy/.env (TF_VAR_smtp_user)."
  type        = string
}

variable "smtp_password" {
  description = "Brevo's SMTP key, as SMTP_PASSWORD in deploy/.env (TF_VAR_smtp_password)."
  type        = string
  sensitive   = true
}

variable "mail_from" {
  description = "The e-mails' sender, on a domain validated at Brevo, as in MAIL_FROM."
  type        = string
  default     = "ne-pas-repondre@sibylle.cc"
}

variable "mail_from_name" {
  description = "The name shown with that sender, as in ../dev-realm.json."
  type        = string
  default     = "La Gazette de Sibylle"
}
