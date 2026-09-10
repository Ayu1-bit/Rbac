"""
Enhanced Shopify Admin REST API client.
- Better error handling and rate limit respecting
- Incremental sync support (updated_since parameter)
- Retry logic with exponential backoff
- Request/response logging for debugging
"""
import requests
import time
import logging
from typing import Optional, List, Dict, Any
from requests.exceptions import RequestException

from utils.db import get_setting, set_setting
from utils.shopify_oauth import normalize_shop_domain, refresh_offline_token

logger = logging.getLogger(__name__)


class ShopifyClient:
    def __init__(self, max_retries: int = 3):
        self.store = get_setting("shopify_store_url", "").strip().rstrip("/")
        self.token = get_setting("shopify_access_token", "").strip()
        self.version = get_setting("shopify_api_version", "2024-10").strip()
        self.max_retries = max_retries
        self.rate_limit_reset = 0

    def _refresh_if_needed(self):
        from datetime import datetime, timezone, timedelta
        exp = get_setting("shopify_token_expires_at", "")
        refresh_token = get_setting("shopify_refresh_token", "")
        client_id = get_setting("shopify_client_id", "")
        client_secret = get_setting("shopify_client_secret", "")
        if not (exp and refresh_token and client_id and client_secret):
            return
        try:
            expiry = datetime.fromisoformat(exp.replace("Z","+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry - datetime.now(timezone.utc) <= timedelta(minutes=5):
                payload = refresh_offline_token(self.store, client_id, client_secret, refresh_token)
                set_setting("shopify_access_token", payload["access_token"])
                set_setting("shopify_refresh_token", payload.get("refresh_token", refresh_token))
                if payload.get("expires_in"):
                    set_setting("shopify_token_expires_at", (datetime.now(timezone.utc)+timedelta(seconds=int(payload["expires_in"]))).isoformat())
                if payload.get("refresh_token_expires_in"):
                    set_setting("shopify_refresh_expires_at", (datetime.now(timezone.utc)+timedelta(seconds=int(payload["refresh_token_expires_in"]))).isoformat())
                self.token = payload["access_token"]
        except Exception as exc:
            logger.warning("Shopify token refresh failed: %s", exc)

    @property
    def configured(self):
        return bool(self.store and self.token)

    @property
    def base_url(self):
        store = normalize_shop_domain(self.store)
        return f"https://{store}/admin/api/{self.version}"

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def _handle_rate_limit(self, headers: Dict[str, str]):
        """Respect Shopify rate limiting"""
        if "X-Shopify-Shop-Api-Call-Limit" in headers:
            limit_header = headers.get("X-Shopify-Shop-Api-Call-Limit", "0/40")
            used, available = map(int, limit_header.split("/"))
            logger.debug(f"Rate limit: {used}/{available}")
            if used >= available - 5:  # Leave buffer
                reset_time = headers.get("X-Shopify-Retry-After", "5")
                sleep_time = float(reset_time) + 1
                logger.warning(f"Rate limit near, sleeping {sleep_time}s")
                time.sleep(sleep_time)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic and rate limiting"""
        self._refresh_if_needed()
        url = f"{self.base_url}{path}"
        headers = self._headers()
        headers.update(kwargs.pop("headers", {}))

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method, url, headers=headers, timeout=30, **kwargs
                )

                # Handle rate limiting
                self._handle_rate_limit(response.headers)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limited, retrying after {retry_after}s")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json() if response.content else {}

            except RequestException as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed after {self.max_retries} retries: {e}")
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", path, params=params or {})

    def _post(self, path: str, payload: Dict) -> Dict:
        return self._request("POST", path, json=payload)

    def _put(self, path: str, payload: Dict) -> Dict:
        return self._request("PUT", path, json=payload)

    def test_connection(self) -> Dict:
        """Test API connection"""
        data = self._get("/shop.json")
        return data.get("shop", {})

    def fetch_products(
        self, limit: int = 50, updated_since: Optional[str] = None
    ) -> List[Dict]:
        """Fetch products, optionally filtered by update time"""
        params = {"limit": limit}
        if updated_since:
            params["updated_at_min"] = updated_since
        data = self._get("/products.json", params=params)
        return data.get("products", [])

    def fetch_orders(
        self,
        limit: int = 50,
        status: str = "any",
        updated_since: Optional[str] = None
    ) -> List[Dict]:
        """Fetch orders, optionally filtered by update time"""
        params = {"limit": limit, "status": status, "fields": "id,name,created_at,updated_at,financial_status,fulfillment_status,customer,subtotal_price,total_tax,total_price"}
        if updated_since:
            params["updated_at_min"] = updated_since
        data = self._get("/orders.json", params=params)
        return data.get("orders", [])

    def fetch_customers(self, limit: int = 50) -> List[Dict]:
        """Fetch customers"""
        data = self._get("/customers.json", params={"limit": limit})
        return data.get("customers", [])

    def push_product(self, product_payload: Dict) -> Dict:
        """Create a new product on Shopify"""
        return self._post("/products.json", product_payload)

    def update_product(self, product_id: int, product_payload: Dict) -> Dict:
        """Update an existing product"""
        return self._put(f"/products/{product_id}.json", product_payload)

    def update_inventory_level(
        self, inventory_item_id: str, location_id: str, available: int
    ) -> Dict:
        """Update inventory level"""
        payload = {
            "location_id": location_id,
            "inventory_item_id": inventory_item_id,
            "available": available,
        }
        return self._post("/inventory_levels/set.json", payload)

    def fetch_locations(self) -> List[Dict]:
        """Fetch warehouse/location list"""
        data = self._get("/locations.json")
        return data.get("locations", [])
