import streamlit as st
import pandas as pd
from datetime import datetime

from utils.db import init_db, run_query
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Customers · Jewellery ERP", page_icon="👥", layout="wide")
init_db()
require_role("admin", "manager", "sales")
render_sidebar_user_box()
st.title("👥 Customer Management (CRM)")

tab_list, tab_add = st.tabs(["📋 Customer List", "➕ Add Customer"])

with tab_list:
    customers = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
    if not customers:
        st.info("No customers yet — add one in the **Add Customer** tab, or sync from Shopify.")
    else:
        search = st.text_input("Search by name / phone / email")
        df = pd.DataFrame(customers)
        if search:
            mask = (df["name"].str.contains(search, case=False, na=False) |
                    df["phone"].fillna("").str.contains(search, case=False, na=False) |
                    df["email"].fillna("").str.contains(search, case=False, na=False))
            df = df[mask]

        # enrich with order stats
        orders = run_query("SELECT customer_id, total_amount, status FROM orders", fetch=True)
        odf = pd.DataFrame(orders) if orders else pd.DataFrame(columns=["customer_id", "total_amount", "status"])

        rows = []
        for _, c in df.iterrows():
            corders = odf[(odf["customer_id"] == c["id"]) & (odf["status"] != "cancelled")] if len(odf) else odf
            rows.append({
                "Name": c["name"], "Phone": c["phone"], "Email": c["email"],
                "City": c["city"], "Orders": len(corders),
                "Total Spent": currency(corders["total_amount"].sum() if len(corders) else 0),
                "Loyalty Pts": c["loyalty_points"],
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Customer 360° View")
        opts = {c["name"]: c["id"] for c in customers}
        chosen = st.selectbox("Select a customer", list(opts.keys()))
        cid = opts[chosen]
        cust = run_query("SELECT * FROM customers WHERE id=?", (cid,), fetchone=True)
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Phone:** {cust['phone'] or '—'}")
            st.write(f"**Email:** {cust['email'] or '—'}")
            st.write(f"**Address:** {cust['address'] or '—'}, {cust['city'] or ''} {cust['pincode'] or ''}")
        with c2:
            st.write(f"**Loyalty Points:** {cust['loyalty_points']}")
            st.write(f"**Shopify Customer ID:** {cust['shopify_customer_id'] or '—'}")

        hist = run_query("SELECT * FROM orders WHERE customer_id=? ORDER BY order_date DESC", (cid,), fetch=True)
        if hist:
            hdf = pd.DataFrame(hist)[["order_number", "order_date", "status", "total_amount"]]
            hdf.columns = ["Order #", "Date", "Status", "Total"]
            hdf["Total"] = hdf["Total"].apply(currency)
            st.dataframe(hdf, hide_index=True, use_container_width=True)
        else:
            st.caption("No order history yet.")

with tab_add:
    with st.form("add_customer", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name *")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
        with c2:
            address = st.text_input("Address")
            city = st.text_input("City")
            state = st.text_input("State")
            pincode = st.text_input("Pincode")
        submitted = st.form_submit_button("💾 Save Customer", type="primary")
        if submitted:
            if not name:
                st.error("Name is required.")
            else:
                run_query("""INSERT INTO customers (name, email, phone, address, city, state, pincode, created_at)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (name, email, phone, address, city, state, pincode, datetime.now().isoformat()))
                st.success(f"✅ Customer '{name}' added!")
                st.rerun()
