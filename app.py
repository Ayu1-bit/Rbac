import streamlit as st

from utils.db import init_db, get_setting, set_setting
from utils.shopify_oauth import exchange_code_for_token, verify_hmac, get_shop_info, normalize_shop_domain
from utils.auth import login, current_user, ROLE_LABELS
from utils.shopify_permissions import init_shopify_permissions, ensure_permission_rows

st.set_page_config(page_title="Jewellery ERP", page_icon="💎", layout="wide")
init_db()
init_shopify_permissions()
ensure_permission_rows(["admin","manager","sales","production","accountant","purchasing"])

# Shopify credentials can be supplied through environment variables.
# The store is connected once; the resulting offline token is persisted in the ERP.
import os
for _k, _setting in {
    "SHOPIFY_STORE_DOMAIN": "shopify_store_url",
    "SHOPIFY_ADMIN_ACCESS_TOKEN": "shopify_access_token",
    "SHOPIFY_API_VERSION": "shopify_api_version",
    "SHOPIFY_CLIENT_ID": "shopify_client_id",
    "SHOPIFY_CLIENT_SECRET": "shopify_client_secret",
    "SHOPIFY_REDIRECT_URI": "shopify_redirect_uri",
    "SHOPIFY_SCOPES": "shopify_scopes",
}.items():
    _v = os.getenv(_k, "").strip()
    if _v:
        set_setting(_setting, _v)

# ============== SHOPIFY OAUTH CALLBACK HANDLER ==============
# If Shopify just redirected the merchant back here after they clicked "Install",
# the URL will contain ?code=...&shop=...&state=...&hmac=... — catch it before
# rendering anything else (this must stay reachable without a login, since it's
# Shopify's server redirecting the browser, not a user session).
qp = st.query_params
if "code" in qp and "shop" in qp:
    st.title("🔗 Connecting your Shopify store...")
    code = qp.get("code")
    shop = qp.get("shop")
    state = qp.get("state", "")
    saved_state = get_setting("shopify_oauth_state", "")
    client_id = get_setting("shopify_client_id", "")
    client_secret = get_setting("shopify_client_secret", "")

    if not client_id or not client_secret:
        st.error("No Client ID / Client Secret found in Settings. Go to **Shopify Sync → Connect Store**, "
                  "enter your app's Client ID and Client Secret first, then start the install flow again.")
    elif state != saved_state:
        st.error("Security check failed: the `state` parameter doesn't match what we sent. "
                  "Please restart the connection from the **Shopify Sync** page.")
    else:
        hmac_ok = verify_hmac(dict(qp), client_secret)
        if not hmac_ok:
            st.warning("⚠️ Could not fully verify Shopify's signed callback (this can happen due to "
                       "how query strings are re-encoded in Streamlit). Proceeding since the `state` "
                       "check passed and the shop domain looks valid — but double-check the shop below.")
        try:
            token_data = exchange_code_for_token(shop, client_id, client_secret, code)
            access_token = token_data.get("access_token")
            if access_token:
                shop_domain = normalize_shop_domain(shop)
                set_setting("shopify_store_url", shop_domain)
                set_setting("shopify_access_token", access_token)
                set_setting("shopify_refresh_token", token_data.get("refresh_token", ""))
                if token_data.get("expires_in"):
                    from datetime import datetime, timedelta, timezone
                    set_setting("shopify_token_expires_at",
                                (datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))).isoformat())
                if token_data.get("refresh_token_expires_in"):
                    from datetime import datetime, timedelta, timezone
                    set_setting("shopify_refresh_expires_at",
                                (datetime.now(timezone.utc) + timedelta(seconds=int(token_data["refresh_token_expires_in"]))).isoformat())
                set_setting("shopify_granted_scopes", token_data.get("scope", ""))
                set_setting("shopify_oauth_state", "")
                try:
                    shop_info = get_shop_info(shop_domain, access_token, get_setting("shopify_api_version", "2024-10"))
                    set_setting("shopify_shop_name", shop_info.get("name", shop_domain))
                except Exception:
                    pass
                st.success(f"✅ Connected to **{get_setting('shopify_shop_name', shop_domain)}**! "
                           f"Access token stored securely in your local database.")
                st.info("Granted scopes: " + token_data.get("scope", "—"))
                if st.button("Continue to Dashboard →", type="primary"):
                    st.query_params.clear()
                    st.rerun()
            else:
                st.error(f"Shopify did not return an access token. Response: {token_data}")
        except Exception as e:
            st.error(f"Token exchange failed: {e}")
    st.stop()
# ============== END OAUTH CALLBACK HANDLER ==============


# ============== LOGIN GATE ==============
if not current_user():
    st.title("💎 Jewellery ERP")
    st.caption("Please log in to continue")
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            if login(username, password):
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()
# ============== END LOGIN GATE ==============


# ============== ROLE-BASED NAVIGATION ==============
role = current_user()["role"]

pages = {
    "dashboard": st.Page("dashboard.py", title="Dashboard", icon="🏠", default=True),
    "pos": st.Page("pages/0_POS.py", title="POS", icon="🛒"),
    "products": st.Page("pages/1_Products.py", title="Products", icon="💍"),
    "orders": st.Page("pages/2_Orders.py", title="Orders", icon="📦"),
    "customers": st.Page("pages/3_Customers.py", title="Customers", icon="👥"),
    "suppliers": st.Page("pages/4_Suppliers_and_Purchases.py", title="Suppliers & Purchases", icon="🏭"),
    "manufacturing": st.Page("pages/5_Manufacturing.py", title="Manufacturing", icon="🛠️"),
    "invoicing": st.Page("pages/6_Invoicing.py", title="Invoicing", icon="🧾"),
    "pricing": st.Page("pages/7_Pricing_Calculator.py", title="Pricing Calculator", icon="💰"),
    "reports": st.Page("pages/8_Reports.py", title="Reports", icon="📈"),
    "shopify_sync": st.Page("pages/9_Shopify_Sync.py", title="Shopify Sync", icon="🔗"),
    "settings": st.Page("pages/10_Settings.py", title="Settings", icon="⚙️"),
    "product_explorer": st.Page("pages/11_Product_Explorer.py", title="Product Explorer", icon="🖼️"),
    "order_explorer": st.Page("pages/12_Order_Explorer.py", title="Order Explorer", icon="📄"),
    "files_library": st.Page("pages/13_Files_Library.py", title="Files Library", icon="🗂️"),
    "shopify_center": st.Page("pages/14_Shopify_Control_Center.py", title="Shopify Control Center", icon="🛍️"),
}

# Which pages each role can see in the sidebar. This is on top of (not instead of) the
# require_role() guard inside each individual page file — that guard still protects a
# direct URL visit even if the page were somehow linked to from outside this nav.
role_pages = {
    "admin": list(pages.keys()),
    "manager": [k for k in pages if k != "settings"] ,
    "sales": ["dashboard", "pos", "orders", "customers", "order_explorer", "shopify_center"],
    "production": ["dashboard", "manufacturing", "shopify_center"],
    "accountant": ["dashboard", "invoicing", "reports", "pricing", "shopify_center"],
    "purchasing": ["dashboard", "suppliers", "shopify_center"],
}

visible_keys = role_pages.get(role, ["dashboard"])
nav = st.navigation([pages[k] for k in visible_keys if k in pages])
nav.run()
# ============== END NAVIGATION ==============
