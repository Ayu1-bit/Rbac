import streamlit as st
import pandas as pd
from datetime import datetime, date

from utils.db import init_db, run_query
from utils.helpers import currency, calc_product_price, latest_rate
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Pricing Calculator · Jewellery ERP", page_icon="💰", layout="wide")
init_db()
require_role("admin", "manager", "accountant")
render_sidebar_user_box()
st.title("💰 Metal Rates & Pricing Calculator")

tab_rates, tab_calc, tab_bulk = st.tabs(["🥇 Manage Rates", "🧮 Price Calculator", "🔄 Bulk Repricing"])

with tab_rates:
    st.subheader("Today's Metal Rates")
    rates = run_query("""
        SELECT metal_type, purity, rate_per_gram, MAX(rate_date) as rate_date
        FROM metal_rates GROUP BY metal_type, purity ORDER BY metal_type, purity
    """, fetch=True)
    if rates:
        rdf = pd.DataFrame(rates)
        rdf.columns = ["Metal", "Purity", "Rate/gram", "Last Updated"]
        rdf["Rate/gram"] = rdf["Rate/gram"].apply(currency)
        st.dataframe(rdf, hide_index=True, use_container_width=True)

    st.subheader("Update a rate")
    with st.form("update_rate"):
        c1, c2, c3 = st.columns(3)
        metal = c1.selectbox("Metal", ["Gold", "Silver", "Platinum"])
        purity = c2.text_input("Purity", value="22K")
        new_rate = c3.number_input("New Rate per gram (₹)", min_value=0.0, step=10.0)
        if st.form_submit_button("💾 Save Rate", type="primary"):
            if new_rate > 0:
                run_query("INSERT INTO metal_rates (metal_type, purity, rate_per_gram, rate_date) VALUES (?,?,?,?)",
                          (metal, purity, new_rate, date.today().isoformat()))
                st.success(f"✅ {metal} {purity} rate updated to {currency(new_rate)}/g")
                st.rerun()
            else:
                st.error("Enter a rate greater than 0.")

    st.caption("💡 Tip: Update rates daily before syncing prices to Shopify, since jewellery prices "
               "typically move with the live gold/silver market rate.")

with tab_calc:
    st.subheader("Quick Price Calculator")
    c1, c2, c3 = st.columns(3)
    metal = c1.selectbox("Metal Type", ["Gold", "Silver", "Platinum"], key="calc_metal")
    purity_options = {"Gold": ["24K", "22K", "18K", "14K"], "Silver": ["999", "925"], "Platinum": ["950", "900"]}
    purity = c2.selectbox("Purity", purity_options[metal], key="calc_purity")
    rate = latest_rate(metal, purity)
    c3.metric("Current Rate", currency(rate) + "/g")

    c4, c5, c6 = st.columns(3)
    net_weight = c4.number_input("Net Weight (g)", min_value=0.0, step=0.1)
    making_type = c5.selectbox("Making Charge Type", ["per_gram", "percentage", "fixed"])
    making_value = c6.number_input("Making Charge Value", min_value=0.0, step=1.0)
    stone_cost = st.number_input("Stone / Diamond Cost (₹)", min_value=0.0, step=100.0)

    if net_weight > 0:
        pricing = calc_product_price(net_weight, rate, making_type, making_value, stone_cost)
        st.divider()
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Metal Value", currency(pricing["metal_value"]))
        r2.metric("Making Charges", currency(pricing["making_charge"]))
        r3.metric(f"GST ({pricing['gst_rate']}%)", currency(pricing["gst_amount"]))
        r4.metric("Final Price", currency(pricing["total"]))
    else:
        st.info("Enter a net weight to calculate the price.")

with tab_bulk:
    st.subheader("Bulk Repricing — recalculate all product prices at current rates")
    st.caption("Recomputes selling price for every active product using its stored making-charge "
               "settings and the latest metal rate. Useful after a daily gold/silver rate change.")
    products = run_query("SELECT * FROM products WHERE status='active'", fetch=True)
    if not products:
        st.info("No active products to reprice.")
    else:
        preview_rows = []
        new_prices = {}
        for p in products:
            rate = latest_rate(p["metal_type"], p["purity"])
            pricing = calc_product_price(p["net_weight"], rate, p["making_charge_type"],
                                          p["making_charge_value"], p["stone_cost"] or 0)
            new_prices[p["id"]] = pricing["total"]
            preview_rows.append({
                "SKU": p["sku"], "Name": p["name"], "Old Price": currency(p["selling_price"]),
                "New Price": currency(pricing["total"]),
                "Change": currency(pricing["total"] - p["selling_price"])
            })
        st.dataframe(pd.DataFrame(preview_rows), hide_index=True, use_container_width=True)

        if st.button("⚡ Apply New Prices to All Products", type="primary"):
            for pid, price in new_prices.items():
                run_query("UPDATE products SET selling_price=?, updated_at=? WHERE id=?",
                          (price, datetime.now().isoformat(), pid))
            st.success(f"✅ Repriced {len(new_prices)} products at current metal rates!")
            st.rerun()
