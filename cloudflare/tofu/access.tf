# The Access organisation: one login page for every Access app of the account (Cloudflare has no per-app login page).
# Everything but login_design is as it was before this file existed.

import {
  to = cloudflare_zero_trust_organization.de0ch
  id = local.account
}

resource "cloudflare_zero_trust_organization" "de0ch" {
  account_id                                  = local.account
  name                                        = "Deyao Chen"
  auth_domain                                 = "de0ch.cloudflareaccess.com"
  is_ui_read_only                             = false
  strict_service_token_auth                   = false
  allow_authenticate_via_warp                 = false
  deny_unmatched_requests                     = false
  auto_redirect_to_identity                   = false
  deny_unmatched_requests_exempted_zone_names = []
  # Cloudflare's own sign-in page, branded (Deyao, 2026-10-28): the Jarvis 4 icon (DE0CH/jarvis4 app/assets/icon.png at a
  # pinned commit, so a later edit of the icon can't change this page unseen) on its own dark navy, white text.
  # No header text: Cloudflare draws it in a box above the sign-in buttons that reads as a button (Deyao, 2026-11-12)
  login_design = {
    background_color = "#04090F"
    text_color       = "#FFFFFF"
    logo_path        = "https://raw.githubusercontent.com/DE0CH/jarvis4/a47aadde23fe8355b30e6ba44dd9376be86a3fbd/app/assets/icon.png"
    footer_text      = "Private systems of Deyao Chen. Authorised users only."
  }
  # off; a PUT must carry all three fields (Cloudflare 12062 "service_token_inactivity must include enabled,
  # inactivity_threshold_days, and action"), so the two that don't apply while it is off are set too
  service_token_inactivity = { enabled = false, action = "disable", inactivity_threshold_days = 90 }
}
