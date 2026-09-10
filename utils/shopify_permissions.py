
"""Role-based access control for Shopify data inside the Jewellery ERP.

Shopify OAuth scopes control what the ERP can do at the store level.
These permissions control what an ERP user can see/change after the data
is available to the ERP.
"""
from utils.db import run_query

SHOPIFY_RESOURCES = [
    ("overview", "Store / Overview"),
    ("products", "Products"),
    ("product_variants", "Product Variants"),
    ("collections", "Collections"),
    ("inventory", "Inventory"),
    ("locations", "Locations"),
    ("orders", "Orders"),
    ("order_edits", "Order Edits"),
    ("customers", "Customers"),
    ("draft_orders", "Draft Orders"),
    ("fulfillments", "Fulfillments"),
    ("returns", "Returns"),
    ("discounts", "Discounts"),
    ("gift_cards", "Gift Cards"),
    ("files", "Files / Media"),
    ("content", "Online Store Content"),
    ("navigation", "Navigation"),
    ("themes", "Themes"),
    ("metafields", "Metafields / Metaobjects"),
    ("markets", "Markets"),
    ("shipping", "Shipping"),
    ("payments", "Payments / Payouts"),
    ("reports", "Reports / Analytics"),
    ("marketing", "Marketing"),
    ("subscriptions", "Subscriptions"),
    ("companies", "B2B Companies"),
    ("locales", "Locales / Translations"),
    ("pixels", "Pixels"),
    ("fulfillment_services", "Fulfillment Services"),
    ("shopify_settings", "Shopify Store Settings"),
]

ACTIONS = ("view", "create", "edit", "delete", "sync")

# Scope -> internal resource. Used to explain why a resource may be unavailable.
RESOURCE_SCOPES = {
    "products": ("read_products", "write_products"),
    "product_variants": ("read_products", "write_products"),
    "collections": ("read_products", "write_products"),
    "inventory": ("read_inventory", "write_inventory"),
    "locations": ("read_locations", "write_locations"),
    "orders": ("read_orders", "write_orders"),
    "order_edits": ("read_order_edits", "write_order_edits"),
    "customers": ("read_customers", "write_customers"),
    "draft_orders": ("read_draft_orders", "write_draft_orders"),
    "fulfillments": ("read_fulfillments", "write_fulfillments"),
    "returns": ("read_returns", "write_returns"),
    "discounts": ("read_discounts", "write_discounts"),
    "gift_cards": ("read_gift_cards", "write_gift_cards"),
    "files": ("read_files", "write_files"),
    "content": ("read_content", "write_content"),
    "navigation": ("read_online_store_navigation", "write_online_store_navigation"),
    "themes": ("read_themes", "write_themes"),
    "metafields": ("read_metaobjects", "write_metaobjects"),
    "markets": ("read_markets", "write_markets"),
    "shipping": ("read_shipping", "write_shipping"),
    "payments": ("read_shopify_payments_payouts", "read_shopify_payments_accounts"),
    "reports": ("read_reports", "write_reports"),
    "marketing": ("read_marketing_events", "write_marketing_events"),
    "companies": ("read_companies", "write_companies"),
    "locales": ("read_locales", "write_locales"),
    "pixels": ("read_pixels", "write_pixels"),
    "fulfillment_services": ("read_custom_fulfillment_services", "write_custom_fulfillment_services"),
    "shopify_settings": ("read_shopify_payments_accounts", "write_content"),
}

def init_shopify_permissions():
    run_query("""CREATE TABLE IF NOT EXISTS shopify_role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        resource TEXT NOT NULL,
        can_view INTEGER DEFAULT 0,
        can_create INTEGER DEFAULT 0,
        can_edit INTEGER DEFAULT 0,
        can_delete INTEGER DEFAULT 0,
        can_sync INTEGER DEFAULT 0,
        UNIQUE(role, resource)
    )""")

def ensure_permission_rows(roles):
    init_shopify_permissions()
    for role in roles:
        for resource, _ in SHOPIFY_RESOURCES:
            run_query("""INSERT OR IGNORE INTO shopify_role_permissions
                (role, resource, can_view, can_create, can_edit, can_delete, can_sync)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (role, resource, 1 if role == "admin" else 0,
                 1 if role == "admin" else 0, 1 if role == "admin" else 0,
                 1 if role == "admin" else 0, 1 if role == "admin" else 0))

def get_permissions(role):
    ensure_permission_rows([role])
    rows = run_query("SELECT * FROM shopify_role_permissions WHERE role=?",
                     (role,), fetch=True)
    return {r["resource"]: r for r in rows}

def can(role, resource, action="view"):
    if role == "admin":
        return True
    row = get_permissions(role).get(resource)
    if not row:
        return False
    col = {"view":"can_view", "create":"can_create", "edit":"can_edit",
           "delete":"can_delete", "sync":"can_sync"}.get(action, "can_view")
    return bool(row[col])

def save_permissions(role, matrix):
    init_shopify_permissions()
    for resource, values in matrix.items():
        run_query("""INSERT INTO shopify_role_permissions
            (role, resource, can_view, can_create, can_edit, can_delete, can_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role, resource) DO UPDATE SET
              can_view=excluded.can_view, can_create=excluded.can_create,
              can_edit=excluded.can_edit, can_delete=excluded.can_delete,
              can_sync=excluded.can_sync""",
            (role, resource, int(values.get("view",0)), int(values.get("create",0)),
             int(values.get("edit",0)), int(values.get("delete",0)), int(values.get("sync",0))))

def granted_scopes():
    raw = run_query("SELECT value FROM settings WHERE key='shopify_granted_scopes'",
                    fetchone=True)
    if not raw or not raw.get("value"):
        return set()
    return {x.strip() for x in raw["value"].split(",") if x.strip()}

def scope_available(resource, action="view"):
    if resource not in RESOURCE_SCOPES:
        return True
    read_scope, write_scope = RESOURCE_SCOPES[resource]
    scopes = granted_scopes()
    if not scopes:
        return True  # legacy/manual installations may not have scope metadata
    return read_scope in scopes if action == "view" or action == "sync" else write_scope in scopes
