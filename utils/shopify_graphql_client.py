
"""Shopify Admin GraphQL client used by the universal Shopify Control Center."""
import requests, json, time
from datetime import datetime, timezone, timedelta
from utils.shopify_oauth import refresh_offline_token
from utils.db import get_setting, set_setting
from utils.shopify_oauth import normalize_shop_domain

class ShopifyGraphQLClient:
    def __init__(self):
        self.store = normalize_shop_domain(get_setting("shopify_store_url", "")).strip("/")
        self.token = get_setting("shopify_access_token", "").strip()
        self.version = get_setting("shopify_api_version", "2026-07").strip() or "2026-07"

    @property
    def configured(self):
        return bool(self.store and self.token)

    @property
    def endpoint(self):
        return f"https://{self.store}/admin/api/{self.version}/graphql.json"

    def execute(self, query, variables=None):
        if not self.configured:
            raise RuntimeError("Shopify is not connected.")
        self.refresh_if_needed()
        r = requests.post(
            self.endpoint,
            headers={"X-Shopify-Access-Token": self.token,
                     "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=60,
        )
        if r.status_code == 429:
            time.sleep(float(r.headers.get("Retry-After", "2")))
            r = requests.post(self.endpoint,
                headers={"X-Shopify-Access-Token": self.token,
                         "Content-Type": "application/json"},
                json={"query": query, "variables": variables or {}}, timeout=60)
        r.raise_for_status()
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(json.dumps(payload["errors"], indent=2))
        return payload.get("data", {})
