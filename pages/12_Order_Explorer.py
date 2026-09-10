import streamlit as st
import pandas as pd

from utils.db import init_db, get_setting
from utils.shopify_graphql import fetch_orders_full
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Order Explorer · Jewellery ERP", page_icon="📄", layout="wide")
init_db()
require_role("admin", "manager", "sales")
render_sidebar_user_box()
st.title("📄 Shopify Order Explorer")
st.caption("Live, complete order detail from Shopify — customer, addresses, line-item images, fulfillment, and totals.")

if not get_setting("shopify_access_token"):
    st.warning("Not connected to Shopify yet. Go to **Shopify Sync** to connect your store first.")
    st.stop()

c1, c2 = st.columns([1, 3])
count = c1.slider("Orders to load", 5, 100, 20)
if c1.button("🔄 Refresh from Shopify", type="primary"):
    st.session_state.pop("order_explorer_data", None)

if "order_explorer_data" not in st.session_state:
    try:
        with st.spinner("Fetching orders from Shopify..."):
            st.session_state.order_explorer_data = fetch_orders_full(first=count)
    except Exception as e:
        st.error(f"Could not fetch orders: {e}")
        st.stop()

data = st.session_state.order_explorer_data
edges = data.get("edges", [])
search = c2.text_input("Filter by order # / customer name / tag")

if not edges:
    st.info("No orders found in your store yet.")
else:
    for edge in edges:
        o = edge["node"]
        cust = o.get("customer") or {}
        cust_name = f"{cust.get('firstName') or ''} {cust.get('lastName') or ''}".strip() or "Guest"
        tags = o.get("tags") or []
        if search:
            haystack = f"{o['name']} {cust_name} {' '.join(tags)}".lower()
            if search.lower() not in haystack:
                continue

        money = o.get("totalPriceSet", {}).get("shopMoney", {})
        total_str = f"{money.get('currencyCode','')} {money.get('amount','0')}"

        with st.container(border=True):
            top1, top2, top3 = st.columns([2, 2, 1])
            top1.subheader(o["name"])
            top1.caption(f"Placed: {o.get('createdAt','')[:10]}")
            top2.write(f"**Customer:** {cust_name}")
            top2.write(f"{cust.get('email') or ''} · {cust.get('phone') or ''}")
            top3.metric("Total", total_str)
            st.write(
                f"**Payment:** {o.get('displayFinancialStatus')} &nbsp;|&nbsp; "
                f"**Fulfillment:** {o.get('displayFulfillmentStatus')}"
            )
            if tags:
                st.write(" ".join([f"`{t}`" for t in tags]))
            if o.get("note"):
                st.info(f"📝 Note: {o['note']}")

            items_tab, addr_tab, fulfill_tab, money_tab = st.tabs(
                ["🛍️ Line Items", "📍 Addresses", "🚚 Fulfillment", "💰 Totals"]
            )

            with items_tab:
                items = [n["node"] for n in o.get("lineItems", {}).get("edges", [])]
                for it in items:
                    ic1, ic2 = st.columns([1, 5])
                    with ic1:
                        img = (it.get("image") or {}).get("url")
                        if img:
                            st.image(img, use_container_width=True)
                    with ic2:
                        price = it.get("originalUnitPriceSet", {}).get("shopMoney", {})
                        st.write(f"**{it['title']}**  ·  SKU: {it.get('sku') or '—'}")
                        st.write(f"Qty: {it['quantity']}  ·  Unit price: {price.get('currencyCode','')} {price.get('amount','')}")
                    st.divider()

            with addr_tab:
                ca1, ca2 = st.columns(2)
                ship = o.get("shippingAddress") or {}
                bill = o.get("billingAddress") or {}
                with ca1:
                    st.markdown("**Shipping Address**")
                    if ship:
                        st.write(f"{ship.get('address1','')} {ship.get('address2','') or ''}")
                        st.write(f"{ship.get('city','')}, {ship.get('province','')} {ship.get('zip','')}")
                        st.write(ship.get("country", ""))
                        st.write(ship.get("phone", ""))
                    else:
                        st.caption("No shipping address.")
                with ca2:
                    st.markdown("**Billing Address**")
                    if bill:
                        st.write(f"{bill.get('address1','')} {bill.get('address2','') or ''}")
                        st.write(f"{bill.get('city','')}, {bill.get('province','')} {bill.get('zip','')}")
                        st.write(bill.get("country", ""))
                    else:
                        st.caption("No billing address.")

            with fulfill_tab:
                fulfillments = o.get("fulfillments", [])
                if fulfillments:
                    for f in fulfillments:
                        st.write(f"**Status:** {f.get('status')}")
                        for t in f.get("trackingInfo", []) or []:
                            st.write(f"Tracking: {t.get('company','')} — {t.get('number','')} — {t.get('url','')}")
                else:
                    st.caption("Not yet fulfilled.")

            with money_tab:
                def fmt(field):
                    m = o.get(field, {}).get("shopMoney", {})
                    return f"{m.get('currencyCode','')} {m.get('amount','0')}"
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Subtotal", fmt("subtotalPriceSet"))
                mc2.metric("Tax", fmt("totalTaxSet"))
                mc3.metric("Discounts", fmt("totalDiscountsSet"))
                mc4.metric("Total", fmt("totalPriceSet"))

    page_info = data.get("pageInfo", {})
    if page_info.get("hasNextPage"):
        if st.button("⬇️ Load more orders"):
            more = fetch_orders_full(first=count, after=page_info.get("endCursor"))
            st.session_state.order_explorer_data["edges"].extend(more["edges"])
            st.session_state.order_explorer_data["pageInfo"] = more["pageInfo"]
            st.rerun()
