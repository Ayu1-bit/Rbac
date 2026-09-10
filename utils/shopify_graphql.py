"""
Shopify Admin GraphQL client — used for rich data the REST API can't fully express:
images, media (incl. 3D models / video), variants with options, full order details
(customer, addresses, fulfillments, discounts, refunds), and the account Files library.
"""
import requests
from utils.db import get_setting


class ShopifyGraphQL:
    def __init__(self):
        self.store = get_setting("shopify_store_url", "").strip().rstrip("/")
        self.token = get_setting("shopify_access_token", "").strip()
        self.version = get_setting("shopify_api_version", "2024-10").strip()

    @property
    def configured(self):
        return bool(self.store and self.token)

    @property
    def endpoint(self):
        store = self.store.replace("https://", "").replace("http://", "")
        return f"https://{store}/admin/api/{self.version}/graphql.json"

    def query(self, query_str, variables=None):
        r = requests.post(
            self.endpoint,
            headers={"X-Shopify-Access-Token": self.token, "Content-Type": "application/json"},
            json={"query": query_str, "variables": variables or {}},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(str(data["errors"]))
        return data["data"]


PRODUCTS_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after, sortKey: UPDATED_AT, reverse: true) {
    edges {
      cursor
      node {
        id
        title
        vendor
        productType
        status
        tags
        descriptionHtml
        totalInventory
        onlineStoreUrl
        images(first: 10) {
          edges { node { url altText } }
        }
        media(first: 10) {
          edges {
            node {
              mediaContentType
              alt
              ... on MediaImage { image { url } }
              ... on Model3d { sources { url format } }
              ... on Video { sources { url } }
            }
          }
        }
        variants(first: 25) {
          edges {
            node {
              id
              title
              sku
              price
              compareAtPrice
              inventoryQuantity
              selectedOptions { name value }
            }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

ORDERS_QUERY = """
query Orders($first: Int!, $after: String) {
  orders(first: $first, after: $after, sortKey: CREATED_AT, reverse: true) {
    edges {
      cursor
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        tags
        note
        totalPriceSet { shopMoney { amount currencyCode } }
        subtotalPriceSet { shopMoney { amount currencyCode } }
        totalTaxSet { shopMoney { amount currencyCode } }
        totalDiscountsSet { shopMoney { amount currencyCode } }
        customer { id firstName lastName email phone }
        shippingAddress { address1 address2 city province zip country phone }
        billingAddress { address1 address2 city province zip country }
        lineItems(first: 25) {
          edges {
            node {
              title
              quantity
              sku
              originalUnitPriceSet { shopMoney { amount currencyCode } }
              image { url }
            }
          }
        }
        fulfillments(first: 5) {
          status
          trackingInfo { number url company }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

FILES_QUERY = """
query Files($first: Int!, $after: String) {
  files(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        alt
        createdAt
        ... on GenericFile { url mimeType originalFileSize }
        ... on MediaImage { image { url } mimeType: mimeType }
        ... on Model3d { sources { url format } }
        ... on Video { sources { url } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def fetch_products_full(first=20, after=None):
    client = ShopifyGraphQL()
    data = client.query(PRODUCTS_QUERY, {"first": first, "after": after})
    return data["products"]


def fetch_orders_full(first=20, after=None):
    client = ShopifyGraphQL()
    data = client.query(ORDERS_QUERY, {"first": first, "after": after})
    return data["orders"]


def fetch_files_full(first=30, after=None):
    client = ShopifyGraphQL()
    data = client.query(FILES_QUERY, {"first": first, "after": after})
    return data["files"]
