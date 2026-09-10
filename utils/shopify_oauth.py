"""
Shopify OAuth ("Install App") flow.

Standard flow:
  1. Merchant enters their store domain in our app.
  2. We build an /admin/oauth/authorize URL and send them there.
  3. Merchant clicks "Install" on Shopify's consent screen.
  4. Shopify redirects back to our `redirect_uri` with ?code=...&shop=...&state=...&hmac=...
  5. We exchange the code for an offline Admin API access token and persist its refresh credentials when Shopify returns an expiring token.

IMPORTANT: `redirect_uri` must be a public HTTPS URL that matches EXACTLY what is
registered in the Shopify Partner Dashboard for this app (App setup > URLs).
`localhost` will NOT work — Shopify's servers must be able to reach it.
"""
import hashlib
import hmac as hmac_lib
import secrets
import requests
from urllib.parse import urlencode


def normalize_shop_domain(raw):
    """Turn 'my-store', 'my-store.myshopify.com', or a full URL into 'my-store.myshopify.com'."""
    if not raw:
        return ""
    s = raw.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    s = s.split("/")[0]
    if s.endswith(".myshopify.com"):
        return s
    if "." in s:
        # a custom domain was entered — Shopify OAuth generally still needs the myshopify.com
        # domain, so we pass it through as-is and let Shopify resolve/redirect if possible.
        return s
    return f"{s}.myshopify.com"


def generate_state():
    return secrets.token_urlsafe(24)


def build_authorize_url(shop, client_id, redirect_uri, scopes, state):
    shop_domain = normalize_shop_domain(shop)
    params = {
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
        "grant_options[]": "value",  # offline access
    }
    return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"


def exchange_code_for_token(shop, client_id, client_secret, code):
    """Returns dict: {'access_token': ..., 'scope': ...}"""
    shop_domain = normalize_shop_domain(shop)
    url = f"https://{shop_domain}/admin/oauth/access_token"
    resp = requests.post(url, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "expiring": "1",
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()


def verify_hmac(query_params: dict, client_secret: str) -> bool:
    """
    Best-effort verification of Shopify's signed callback query string.
    Note: because Streamlit re-parses/re-encodes query params, this may not byte-match
    Shopify's original raw query string in every deployment. Treat a failure here as a
    signal to double check, not an absolute security guarantee on its own — always also
    confirm the `shop` domain matches the one you initiated the flow for.
    """
    if not client_secret or "hmac" not in query_params:
        return False
    provided_hmac = query_params.get("hmac", "")
    items = {k: v for k, v in query_params.items() if k not in ("hmac", "signature")}
    message = "&".join(f"{k}={v}" for k, v in sorted(items.items()))
    digest = hmac_lib.new(
        client_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(digest, provided_hmac)


def get_shop_info(shop, access_token, api_version="2024-10"):
    shop_domain = normalize_shop_domain(shop)
    url = f"https://{shop_domain}/admin/api/{api_version}/shop.json"
    resp = requests.get(url, headers={"X-Shopify-Access-Token": access_token}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("shop", {})


def refresh_offline_token(shop, client_id, client_secret, refresh_token):
    """Refresh an expiring offline token without asking the merchant to reconnect."""
    shop_domain = normalize_shop_domain(shop)
    url = f"https://{shop_domain}/admin/oauth/access_token"
    resp = requests.post(url, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()
