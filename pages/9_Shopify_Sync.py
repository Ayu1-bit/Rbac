import streamlit as st
import pandas as pd
from datetime import datetime

from utils.db import init_db, run_query, get_setting, set_setting
from utils.shopify_api import ShopifyClient
from utils.shopify_oauth import build_authorize_url, generate_state, normalize_shop_domain
from utils.shopify_realtime_sync import RealtimeSyncEngine, SyncType
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box, current_user
from utils.shopify_permissions import can, scope_available, SHOPIFY_RESOURCES

st.set_page_config(page_title="Shopify Sync · Jewellery ERP", page_icon="🔗", layout="wide")
init_db()
role = current_user()["role"] if current_user() else ""
if role != "admin" and not can(role, "overview", "view"):
    st.error("Your role does not have access to Shopify.")
    st.stop()
render_sidebar_user_box()
st.title("🔗 Shopify Control Center")
if role != "admin":
    st.info("This page manages the single shared Shopify connection and is restricted to administrators. Use **Shopify Control Center** for your role-based Shopify data access.")
    st.stop()
st.caption("The Shopify connection is shared by the ERP. Admin controls what each role can see, sync and edit.")

# The connection itself is an admin operation; users never receive the Shopify token.
if role != "admin":
    st.info(f"Signed in as **{current_user().get('full_name') or current_user().get('username')}** · Role: **{role}**")

connected = bool(get_setting("shopify_access_token"))

with st.expander("⚙️ Connect Store (OAuth — recommended)", expanded=not connected):
    st.markdown("""
This is the standard **"Install App"** flow: you enter your store domain, click Connect,
approve the install on Shopify's own screen, and your Admin API access token is captured
and stored automatically — no manual token copying.

**One-time setup in the [Shopify Partner Dashboard](https://partners.shopify.com):**
1. Create an app (or use an existing custom/public app).
2. Under **App setup → URLs**, set:
   - **App URL** = the public URL where this Streamlit app is hosted
   - **Allowed redirection URL(s)** = that same public URL, exactly (e.g. `https://your-app.streamlit.app`)
3. Copy the **Client ID** and **Client secret** from the app's API credentials tab into the fields below.

⚠️ **This requires your app to be reachable at a public HTTPS URL** — Shopify's servers
send the merchant's browser back to your `redirect_uri` after they approve the install,
so `localhost` will not work. If you're testing locally, use a tunnel like `ngrok http 8501`
and use the ngrok HTTPS URL as your redirect URI (both here and in the Partner Dashboard).
""")
    c1, c2 = st.columns(2)
    client_id = c1.text_input("Client ID", value=get_setting("shopify_client_id", ""))
    client_secret = c2.text_input("Client Secret", value=get_setting("shopify_client_secret", ""), type="password")
    redirect_uri = st.text_input(
        "Redirect URI (your app's public URL — must match Partner Dashboard exactly)",
        value=get_setting("shopify_redirect_uri", ""),
        placeholder="https://your-app-domain.example.com",
    )
    scopes = st.text_area("API Scopes requested", value=get_setting("shopify_scopes", ""), height=70,
                           help="Comma-separated Shopify scope names. Defaults cover products, orders, "
                                "customers, inventory, fulfillments, files, discounts and more.")

    if st.button("💾 Save App Credentials"):
        set_setting("shopify_client_id", client_id)
        set_setting("shopify_client_secret", client_secret)
        set_setting("shopify_redirect_uri", redirect_uri)
        set_setting("shopify_scopes", scopes)
        st.success("Saved.")

    st.divider()
    store_domain_input = st.text_input("Your store domain", placeholder="your-store.myshopify.com or your-store")

    if st.button("🚀 Connect to Store", type="primary"):
        if not (client_id and client_secret and redirect_uri and store_domain_input):
            st.error("Fill in Client ID, Client Secret, Redirect URI, and your store domain first.")
        else:
            state = generate_state()
            set_setting("shopify_oauth_state", state)
            url = build_authorize_url(store_domain_input, client_id, redirect_uri, scopes, state)
            st.markdown(f"### 👉 [Click here to install the app on {normalize_shop_domain(store_domain_input)}]({url})")
            st.caption("You'll be taken to Shopify's own consent screen. Approve the requested "
                       "permissions, and you'll be redirected back here automatically with your "
                       "access token captured.")

    if connected:
        st.success(f"✅ Currently connected to **{get_setting('shopify_shop_name') or get_setting('shopify_store_url')}**")
        if st.button("🔌 Disconnect Store"):
            set_setting("shopify_access_token", "")
            set_setting("shopify_store_url", "")
            set_setting("shopify_shop_name", "")
            st.success("Disconnected.")
            st.rerun()

with st.expander("🛠️ Advanced: connect with a manual Admin API token instead"):
    st.caption("Use this if you created a **custom app** directly in your store's admin "
               "(Settings → Apps and sales channels → Develop apps) rather than going through "
               "the Partner Dashboard OAuth flow — those tokens are generated for you to paste "
               "directly, no redirect needed.")
    c1, c2 = st.columns(2)
    store_url = c1.text_input("Store domain ", value=get_setting("shopify_store_url", ""),
                               placeholder="your-store.myshopify.com", key="manual_store")
    token = c2.text_input("Admin API access token ", value="", type="password", key="manual_token")
    if st.button("💾 Save Manual Credentials"):
        set_setting("shopify_store_url", normalize_shop_domain(store_url))
        if token:
            set_setting("shopify_access_token", token)
        st.success("Saved. Test the connection below.")
        st.rerun()

client = ShopifyClient()
sync_engine = RealtimeSyncEngine()

if not client.configured:
    st.warning("Enter your Shopify store domain and Admin API access token above to enable syncing.")
else:
    if st.button("🔌 Test Connection"):
        try:
            shop = client.test_connection()
            st.success(f"✅ Connected to **{shop.get('name', client.store)}** ({shop.get('email','')})")
        except Exception as e:
            st.error(f"Connection failed: {e}")

    st.divider()

    # Auto-sync configuration
    with st.expander("⚙️ Auto-Sync Settings (Real-Time)", expanded=False):
        st.caption("Enable automatic background syncing. Data will update automatically without manual intervention.")
        
        col1, col2 = st.columns(2)
        with col1:
            enable_autosync = st.checkbox(
                "Enable automatic syncing",
                value=get_setting("auto_sync_enabled", "false") == "true"
            )
        with col2:
            interval = st.number_input(
                "Sync interval (minutes)",
                min_value=5, max_value=120, value=15,
                help="How often to check Shopify for new data"
            )

        col_prod, col_ord, col_cust = st.columns(3)
        with col_prod:
            sync_products = st.checkbox("Products", value=get_setting("auto_sync_products", "true") == "true")
        with col_ord:
            sync_orders = st.checkbox("Orders", value=get_setting("auto_sync_orders", "true") == "true")
        with col_cust:
            sync_customers = st.checkbox("Customers", value=get_setting("auto_sync_customers", "true") == "true")

        if st.button("💾 Save Auto-Sync Config"):
            set_setting("auto_sync_enabled", "true" if enable_autosync else "false")
            set_setting("auto_sync_interval_minutes", str(interval))
            set_setting("auto_sync_products", "true" if sync_products else "false")
            set_setting("auto_sync_orders", "true" if sync_orders else "false")
            set_setting("auto_sync_customers", "true" if sync_customers else "false")
            
            if enable_autosync:
                st.success(f"✅ Auto-sync enabled every {interval} minutes")
                st.info("💡 **Note:** For background syncing to work, run this command in your production environment:\n"
                       "`python -m jewellery_erp.background_sync_worker`\n\n"
                       "See README.md for deployment instructions.")
            else:
                st.info("Auto-sync disabled")

    st.divider()

    # Manual sync tabs
    tab_products, tab_orders, tab_customers, tab_push, tab_history = st.tabs(
        ["⬇️ Sync Products", "⬇️ Sync Orders", "⬇️ Sync Customers", "⬆️ Push Product", "📊 Sync History"]
    )

    with tab_products:
        st.caption("Manually fetch and sync products from Shopify. Smart conflict detection prevents data loss.")
        col1, col2 = st.columns(2)
        with col1:
            limit = st.slider("Number of products to fetch", 5, 250, 50, key="prod_limit")
            incremental = st.checkbox("Incremental (only updated since last sync)", value=True, help="Faster, syncs only changes")
        
        if st.button("⬇️ Sync Products Now", type="primary", disabled=not can(role, "products", "sync")):
            with st.spinner("Syncing products..."):
                result = sync_engine.sync_products(limit=limit)
                if result["status"] == "completed":
                    st.success(f"✅ Imported {result['imported']}, Updated {result['updated']}")
                    if result.get("errors"):
                        st.warning("⚠️ Some products had errors:")
                        for err in result["errors"][:5]:
                            st.caption(f"• {err}")
                else:
                    st.error(f"❌ Sync failed: {result.get('error')}")

    with tab_orders:
        st.caption("Sync orders from Shopify. Only new and changed orders are imported.")
        col1, col2 = st.columns(2)
        with col1:
            limit = st.slider("Number of orders to fetch", 5, 250, 50, key="order_limit")
        with col2:
            incremental = st.checkbox("Incremental", value=True, key="order_incr")

        if st.button("⬇️ Sync Orders Now", type="primary", disabled=not can(role, "orders", "sync")):
            with st.spinner("Syncing orders..."):
                result = sync_engine.sync_orders(limit=limit, since_last_sync=incremental)
                if result["status"] == "completed":
                    st.success(f"✅ Imported {result['imported']}, Updated {result['updated']}")
                    if result.get("errors"):
                        st.warning("⚠️ Some orders had errors:")
                        for err in result["errors"][:5]:
                            st.caption(f"• {err}")
                else:
                    st.error(f"❌ Sync failed: {result.get('error')}")

    with tab_customers:
        st.caption("Sync customers from Shopify with automatic duplicate detection.")
        limit = st.slider("Number of customers to fetch", 5, 250, 50, key="cust_limit")

        if st.button("⬇️ Sync Customers Now", type="primary", disabled=not can(role, "customers", "sync")):
            with st.spinner("Syncing customers..."):
                result = sync_engine.sync_customers(limit=limit)
                if result["status"] == "completed":
                    st.success(f"✅ Imported {result['imported']}, Updated {result['updated']}")
                    if result.get("errors"):
                        st.warning("⚠️ Some customers had errors:")
                        for err in result["errors"][:5]:
                            st.caption(f"• {err}")
                else:
                    st.error(f"❌ Sync failed: {result.get('error')}")

    with tab_push:
        st.caption("Push a local ERP product to Shopify as a new product listing.")
        local_products = run_query("SELECT * FROM products WHERE shopify_product_id IS NULL OR shopify_product_id = ''", fetch=True)
        if not local_products:
            st.info("All local products are already linked to Shopify (or none exist).")
        else:
            opts = {f"{p['sku']} — {p['name']}": p for p in local_products}
            choice = st.selectbox("Select product to push", list(opts.keys()))
            p = opts[choice]
            st.write(f"Will create: **{p['name']}** — {currency(p['selling_price'])}, stock {p['stock_qty']}")
            if st.button("⬆️ Push to Shopify", type="primary", disabled=not can(role, "products", "create")):
                try:
                    payload = {
                        "product": {
                            "title": p["name"],
                            "product_type": p["category"],
                            "variants": [{
                                "price": str(p["selling_price"]),
                                "sku": p["sku"],
                                "inventory_quantity": p["stock_qty"],
                                "inventory_management": "shopify",
                            }],
                        }
                    }
                    result = client.push_product(payload)
                    new_id = result.get("product", {}).get("id")
                    if new_id:
                        run_query("UPDATE products SET shopify_product_id=? WHERE id=?", (str(new_id), p["id"]))
                        st.success(f"✅ Pushed to Shopify! New Shopify Product ID: {new_id}")
                    else:
                        st.warning(f"Response received but no product ID found: {result}")
                except Exception as e:
                    st.error(f"Push failed: {e}")

    with tab_history:
        st.caption("View sync history and status for audit trail and troubleshooting.")
        
        sync_status = sync_engine.get_sync_status()
        
        # Latest sync status cards
        if sync_status["latest"]:
            cols = st.columns(3)
            sync_types_to_show = ["products", "orders", "customers"]
            for i, sync_type in enumerate(sync_types_to_show):
                if sync_type in sync_status["latest"]:
                    latest = sync_status["latest"][sync_type]
                    with cols[i % 3]:
                        status_icon = "✅" if latest["status"] == "completed" else "❌" if latest["status"] == "failed" else "⏳"
                        st.metric(
                            f"{status_icon} {sync_type.title()}",
                            f"{latest['record_count']} records",
                            latest["sync_timestamp"][-8:]  # Show time only
                        )
        
        st.divider()
        
        # Recent sync history
        if sync_status["history"]:
            df = pd.DataFrame(sync_status["history"])
            df["sync_timestamp"] = pd.to_datetime(df["sync_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            df = df[["sync_type", "status", "record_count", "sync_timestamp"]].head(20)
            df.columns = ["Type", "Status", "Records", "Timestamp"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No sync history yet. Run a manual sync above to get started.")
