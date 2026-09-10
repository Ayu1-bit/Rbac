import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from utils.db import init_db, run_query
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Reports · Jewellery ERP", page_icon="📈", layout="wide")
init_db()
require_role("admin", "manager", "accountant")
render_sidebar_user_box()
st.title("📈 Reports & Analytics")

tab_sales, tab_inv, tab_profit, tab_karigar = st.tabs(
    ["💵 Sales Report", "📦 Inventory Valuation", "📊 Profit Margin", "🛠️ Karigar Performance"]
)

# ---------------- SALES ----------------
with tab_sales:
    orders = run_query("SELECT * FROM orders WHERE status != 'cancelled'", fetch=True)
    if not orders:
        st.info("No sales data yet.")
    else:
        df = pd.DataFrame(orders)
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df = df.dropna(subset=["order_date"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Revenue", currency(df["total_amount"].sum()))
        c2.metric("Total Orders", len(df))
        c3.metric("Avg Order Value", currency(df["total_amount"].mean() if len(df) else 0))

        monthly = df.groupby(df["order_date"].dt.to_period("M"))["total_amount"].sum().reset_index()
        monthly["order_date"] = monthly["order_date"].astype(str)
        fig = px.bar(monthly, x="order_date", y="total_amount", title="Monthly Revenue")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig2 = px.pie(status_counts, names="Status", values="Count", title="Orders by Status")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------- INVENTORY VALUATION ----------------
with tab_inv:
    products = run_query("SELECT * FROM products", fetch=True)
    if not products:
        st.info("No products yet.")
    else:
        df = pd.DataFrame(products)
        df["stock_value_cost"] = df["cost_price"] * df["stock_qty"]
        df["stock_value_selling"] = df["selling_price"] * df["stock_qty"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Units in Stock", int(df["stock_qty"].sum()))
        c2.metric("Inventory Value (Cost)", currency(df["stock_value_cost"].sum()))
        c3.metric("Inventory Value (Selling)", currency(df["stock_value_selling"].sum()))

        by_metal = df.groupby("metal_type").agg(
            total_weight=("net_weight", lambda x: (x * df.loc[x.index, "stock_qty"]).sum()),
            total_value=("stock_value_cost", "sum")
        ).reset_index()
        by_metal.columns = ["Metal", "Total Weight in Stock (g)", "Total Cost Value"]
        by_metal["Total Cost Value"] = by_metal["Total Cost Value"].apply(currency)
        st.subheader("Stock by Metal Type")
        st.dataframe(by_metal, hide_index=True, use_container_width=True)

        by_cat = df.groupby("category")["stock_qty"].sum().reset_index()
        fig = px.bar(by_cat, x="category", y="stock_qty", title="Stock Qty by Category")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- PROFIT MARGIN ----------------
with tab_profit:
    items = run_query("""
        SELECT oi.qty, oi.price, p.cost_price, p.name, p.sku, o.status
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != 'cancelled'
    """, fetch=True)
    if not items:
        st.info("No sales line items yet to compute margins.")
    else:
        df = pd.DataFrame(items)
        df["revenue"] = df["qty"] * df["price"]
        df["cost"] = df["qty"] * df["cost_price"]
        df["profit"] = df["revenue"] - df["cost"]
        df["margin_pct"] = df.apply(lambda r: round((r["profit"] / r["revenue"] * 100), 1) if r["revenue"] else 0, axis=1)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Revenue", currency(df["revenue"].sum()))
        c2.metric("Total Profit", currency(df["profit"].sum()))
        c3.metric("Avg Margin %", f"{df['margin_pct'].mean():.1f}%" if len(df) else "0%")

        by_prod = df.groupby(["sku", "name"]).agg(
            units_sold=("qty", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum")
        ).reset_index().sort_values("profit", ascending=False)
        by_prod["revenue"] = by_prod["revenue"].apply(currency)
        by_prod["profit"] = by_prod["profit"].apply(currency)
        by_prod.columns = ["SKU", "Product", "Units Sold", "Revenue", "Profit"]
        st.subheader("Profit by Product")
        st.dataframe(by_prod, hide_index=True, use_container_width=True)

# ---------------- KARIGAR PERFORMANCE ----------------
with tab_karigar:
    jobs = run_query("SELECT * FROM manufacturing_jobs", fetch=True)
    if not jobs:
        st.info("No manufacturing jobs recorded yet.")
    else:
        df = pd.DataFrame(jobs)
        df["wastage_pct"] = df.apply(
            lambda r: round(((r["given_weight"] - r["received_weight"]) / r["given_weight"] * 100), 2)
            if r["given_weight"] else 0, axis=1)

        summary = df.groupby("karigar_name").agg(
            jobs_count=("job_number", "count"),
            avg_wastage_pct=("wastage_pct", "mean"),
            total_labour_paid=("labour_charge", "sum"),
        ).reset_index().sort_values("jobs_count", ascending=False)
        summary["avg_wastage_pct"] = summary["avg_wastage_pct"].round(2)
        summary["total_labour_paid"] = summary["total_labour_paid"].apply(currency)
        summary.columns = ["Karigar", "Jobs Handled", "Avg Wastage %", "Total Labour Paid"]
        st.dataframe(summary, hide_index=True, use_container_width=True)

        fig = px.bar(df.groupby("karigar_name")["wastage_pct"].mean().reset_index(),
                     x="karigar_name", y="wastage_pct", title="Average Wastage % by Karigar")
        st.plotly_chart(fig, use_container_width=True)
