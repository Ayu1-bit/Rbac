import streamlit as st
import pandas as pd
from datetime import datetime, date

from utils.db import init_db, run_query, next_number
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Suppliers & Purchases · Jewellery ERP", page_icon="🏭", layout="wide")
init_db()
require_role("admin", "manager", "purchasing")
render_sidebar_user_box()
st.title("🏭 Suppliers & Purchase Orders")

tab_sup, tab_po_list, tab_po_new = st.tabs(["🧑‍🤝‍🧑 Suppliers", "📋 Purchase Orders", "➕ New Purchase Order"])

with tab_sup:
    st.subheader("Suppliers")
    suppliers = run_query("SELECT * FROM suppliers ORDER BY name", fetch=True)
    if suppliers:
        sdf = pd.DataFrame(suppliers)[["name", "contact_person", "phone", "material_type", "gst_number"]]
        sdf.columns = ["Name", "Contact", "Phone", "Material", "GSTIN"]
        st.dataframe(sdf, hide_index=True, use_container_width=True)
    else:
        st.info("No suppliers yet. Add one below.")

    with st.form("add_supplier", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("Supplier Name *")
            contact_person = st.text_input("Contact Person")
        with c2:
            phone = st.text_input("Phone")
            email = st.text_input("Email")
        with c3:
            material_type = st.selectbox("Primary Material", ["Gold", "Silver", "Platinum", "Gemstones", "Other"])
            gst_number = st.text_input("GST Number")
        address = st.text_input("Address")
        if st.form_submit_button("💾 Save Supplier", type="primary"):
            if not name:
                st.error("Supplier name is required.")
            else:
                run_query("""INSERT INTO suppliers (name, contact_person, phone, email, address,
                             material_type, gst_number, created_at) VALUES (?,?,?,?,?,?,?,?)""",
                          (name, contact_person, phone, email, address, material_type, gst_number,
                           datetime.now().isoformat()))
                st.success(f"✅ Supplier '{name}' added!")
                st.rerun()

with tab_po_list:
    pos = run_query("""
        SELECT po.*, s.name as supplier_name FROM purchase_orders po
        LEFT JOIN suppliers s ON po.supplier_id = s.id ORDER BY po.po_date DESC
    """, fetch=True)
    if not pos:
        st.info("No purchase orders yet.")
    else:
        pdf = pd.DataFrame(pos)[["po_number", "supplier_name", "po_date", "status", "total_amount"]]
        pdf.columns = ["PO #", "Supplier", "Date", "Status", "Total"]
        pdf["Total"] = pdf["Total"].apply(currency)
        st.dataframe(pdf, hide_index=True, use_container_width=True)

        st.divider()
        opts = {p["po_number"]: p["id"] for p in pos}
        sel = st.selectbox("View / update PO", list(opts.keys()))
        poid = opts[sel]
        current = run_query("SELECT * FROM purchase_orders WHERE id=?", (poid,), fetchone=True)
        items = run_query("SELECT * FROM purchase_items WHERE po_id=?", (poid,), fetch=True)
        if items:
            idf = pd.DataFrame(items)[["material_type", "purity", "weight", "rate_per_gram", "amount"]]
            idf.columns = ["Material", "Purity", "Weight (g)", "Rate/g", "Amount"]
            idf["Amount"] = idf["Amount"].apply(currency)
            st.dataframe(idf, hide_index=True, use_container_width=True)

        new_status = st.selectbox("Update Status", ["draft", "ordered", "received", "cancelled"],
                                   index=["draft", "ordered", "received", "cancelled"].index(current["status"]) if current["status"] in ["draft", "ordered", "received", "cancelled"] else 0)
        if st.button("💾 Update PO Status", type="primary"):
            run_query("UPDATE purchase_orders SET status=? WHERE id=?", (new_status, poid))
            st.success("PO updated ✅")
            st.rerun()

with tab_po_new:
    suppliers = run_query("SELECT * FROM suppliers ORDER BY name", fetch=True)
    if not suppliers:
        st.warning("Add a supplier first in the **Suppliers** tab.")
    else:
        sup_opts = {s["name"]: s["id"] for s in suppliers}
        sup_choice = st.selectbox("Supplier", list(sup_opts.keys()))
        po_date_input = st.date_input("PO Date", value=date.today())

        if "po_items_cart" not in st.session_state:
            st.session_state.po_items_cart = []

        st.markdown("**Add material line items**")
        c1, c2, c3, c4 = st.columns(4)
        material = c1.selectbox("Material", ["Gold", "Silver", "Platinum", "Gemstones", "Other"])
        purity = c2.text_input("Purity", value="22K")
        weight = c3.number_input("Weight (g)", min_value=0.0, step=0.1)
        rate = c4.number_input("Rate / gram (₹)", min_value=0.0, step=10.0)

        if st.button("➕ Add material line"):
            amount = weight * rate
            st.session_state.po_items_cart.append({
                "material_type": material, "purity": purity, "weight": weight,
                "rate_per_gram": rate, "amount": amount
            })

        if st.session_state.po_items_cart:
            cart_df = pd.DataFrame(st.session_state.po_items_cart)
            show = cart_df.copy()
            show["amount"] = show["amount"].apply(currency)
            st.dataframe(show, hide_index=True, use_container_width=True)
            total = cart_df["amount"].sum()
            st.metric("PO Total", currency(total))

            if st.button("🧹 Clear items"):
                st.session_state.po_items_cart = []
                st.rerun()

            if st.button("✅ Create Purchase Order", type="primary"):
                po_number = next_number("PO", "purchase_orders", "po_number")
                poid = run_query("""INSERT INTO purchase_orders (po_number, supplier_id, po_date, status, total_amount)
                                     VALUES (?,?,?,?,?)""",
                                  (po_number, sup_opts[sup_choice], po_date_input.isoformat(), "draft", total))
                for item in st.session_state.po_items_cart:
                    run_query("""INSERT INTO purchase_items (po_id, material_type, purity, weight, rate_per_gram, amount)
                                 VALUES (?,?,?,?,?,?)""",
                              (poid, item["material_type"], item["purity"], item["weight"],
                               item["rate_per_gram"], item["amount"]))
                st.session_state.po_items_cart = []
                st.success(f"✅ Purchase Order {po_number} created!")
                st.rerun()
        else:
            st.caption("Add at least one material line item.")
