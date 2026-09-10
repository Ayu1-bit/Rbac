import streamlit as st
import pandas as pd
import plotly.express as px

from utils.db import init_db, run_query, get_setting
from utils.helpers import currency, stock_status
from utils.auth import require_role, render_sidebar_user_box

init_db()
require_role()  # any logged-in user, any role
render_sidebar_user_box()

st.title(f"💎 {get_setting('company_name', 'Jewellery ERP')} — Dashboard")
st.caption("Complete ERP for managing your Shopify jewellery business")

# ---------- KPI ROW ----------
products = run_query("SELECT * FROM products", fetch=True)
orders = run_query("SELECT * FROM orders", fetch=True)
customers = run_query("SELECT * FROM customers", fetch=True)

total_stock_value = sum((p["cost_price"] or 0) * (p["stock_qty"] or 0) for p in products)
total_revenue = sum((o["total_amount"] or 0) for o in orders if o["status"] != "cancelled")
low_stock = [p for p in products if (p["stock_qty"] or 0) <= (p["reorder_level"] or 2)]
pending_orders = [o for o in orders if o["status"] in ("pending", "processing")]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Products (SKUs)", len(products))
c2.metric("Inventory Value (cost)", currency(total_stock_value))
c3.metric("Total Revenue", currency(total_revenue))
c4.metric("Pending Orders", len(pending_orders))
c5.metric("Customers", len(customers))

st.divider()

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📈 Sales Trend")
    if orders:
        df = pd.DataFrame(orders)
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df = df.dropna(subset=["order_date"])
        if not df.empty:
            daily = df.groupby(df["order_date"].dt.date)["total_amount"].sum().reset_index()
            daily.columns = ["Date", "Revenue"]
            fig = px.line(daily, x="Date", y="Revenue", markers=True)
            fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No dated orders yet. Add orders to see trends.")
    else:
        st.info("No orders yet. Go to **Orders** page to add your first order, or sync from Shopify.")

    st.subheader("💍 Stock by Category")
    if products:
        dfp = pd.DataFrame(products)
        cat = dfp.groupby("category")["stock_qty"].sum().reset_index()
        fig2 = px.bar(cat, x="category", y="stock_qty", color="category")
        fig2.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No products yet. Go to **Products** page to add jewellery items.")

with col_right:
    st.subheader("⚠️ Low Stock Alerts")
    if low_stock:
        for p in low_stock[:10]:
            st.warning(f"**{p['name']}** ({p['sku']}) — {stock_status(p['stock_qty'], p['reorder_level'])} · Qty: {p['stock_qty']}")
    else:
        st.success("All products are sufficiently stocked ✅")

    st.subheader("🥇 Current Metal Rates")
    rates = run_query(
        "SELECT metal_type, purity, rate_per_gram, MAX(rate_date) as rate_date "
        "FROM metal_rates GROUP BY metal_type, purity ORDER BY metal_type", fetch=True
    )
    if rates:
        rdf = pd.DataFrame(rates)[["metal_type", "purity", "rate_per_gram"]]
        rdf.columns = ["Metal", "Purity", "Rate / gram"]
        st.dataframe(rdf, hide_index=True, use_container_width=True)
    st.caption("Update rates on the **Pricing Calculator** page.")

st.divider()
st.subheader("🧾 Recent Orders")
if orders:
    recent = sorted(orders, key=lambda o: o["order_date"] or "", reverse=True)[:8]
    rdf = pd.DataFrame(recent)[["order_number", "order_date", "status", "payment_status", "total_amount"]]
    rdf.columns = ["Order #", "Date", "Status", "Payment", "Total"]
    st.dataframe(rdf, hide_index=True, use_container_width=True)
else:
    st.info("No orders recorded yet.")
