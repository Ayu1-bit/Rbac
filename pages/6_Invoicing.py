import streamlit as st
import pandas as pd
import os
from datetime import datetime, date

from utils.db import init_db, run_query, next_number, get_setting
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box
from utils.pdf import build_invoice_pdf as build_pdf, INVOICE_DIR

st.set_page_config(page_title="Invoicing · Jewellery ERP", page_icon="🧾", layout="wide")
init_db()
require_role("admin", "manager", "accountant")
render_sidebar_user_box()
st.title("🧾 Invoicing")

tab_gen, tab_list = st.tabs(["🆕 Generate Invoice", "📋 Invoice History"])


with tab_gen:
    orders = run_query("""
        SELECT o.*, c.name as customer_name FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.id NOT IN (SELECT order_id FROM invoices WHERE order_id IS NOT NULL)
        ORDER BY o.order_date DESC
    """, fetch=True)

    if not orders:
        st.info("All orders already have invoices, or no orders exist yet. Create an order first.")
    else:
        opts = {f"{o['order_number']} — {o['customer_name'] or 'Walk-in'} — {currency(o['total_amount'])}": o["id"] for o in orders}
        choice = st.selectbox("Select order to invoice", list(opts.keys()))
        oid = opts[choice]
        order = run_query("SELECT * FROM orders WHERE id=?", (oid,), fetchone=True)
        customer = run_query("SELECT * FROM customers WHERE id=?", (order["customer_id"],), fetchone=True) if order["customer_id"] else None
        items = run_query("""
            SELECT oi.*, p.name as product_name FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id=?
        """, (oid,), fetch=True)

        display_items = [{"name": it["product_name"] or "Item", "qty": it["qty"], "price": it["price"]} for it in items] \
            if items else [{"name": "Order total", "qty": 1, "price": order["subtotal"] or order["total_amount"]}]

        st.write(f"**Customer:** {customer['name'] if customer else 'Walk-in Customer'}")
        idf = pd.DataFrame(display_items)
        idf["line_total"] = idf["qty"] * idf["price"]
        show = idf.copy()
        show["price"] = show["price"].apply(currency)
        show["line_total"] = show["line_total"].apply(currency)
        st.dataframe(show, hide_index=True, use_container_width=True)

        subtotal = order["subtotal"] or idf["qty"].mul(idf["price"]).sum()
        gst_amount = order["tax_amount"] or 0
        total = order["total_amount"]
        st.metric("Invoice Total", currency(total))

        if st.button("🧾 Generate Invoice PDF", type="primary"):
            invoice_number = next_number("INV", "invoices", "invoice_number")
            path = build_pdf(invoice_number, order, customer, display_items, subtotal, gst_amount, total)
            run_query("""INSERT INTO invoices (invoice_number, order_id, invoice_date, subtotal, gst_amount, total, pdf_path)
                         VALUES (?,?,?,?,?,?,?)""",
                      (invoice_number, oid, date.today().isoformat(), subtotal, gst_amount, total, path))
            st.success(f"✅ Invoice {invoice_number} generated!")
            with open(path, "rb") as f:
                st.download_button("⬇️ Download Invoice PDF", f, file_name=f"{invoice_number}.pdf", mime="application/pdf")

with tab_list:
    invoices = run_query("""
        SELECT i.*, o.order_number FROM invoices i LEFT JOIN orders o ON i.order_id = o.id
        ORDER BY i.invoice_date DESC
    """, fetch=True)
    if not invoices:
        st.info("No invoices generated yet.")
    else:
        for inv in invoices:
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.write(f"**{inv['invoice_number']}**")
            c2.write(inv["order_number"] or "—")
            c3.write(currency(inv["total"]))
            if inv["pdf_path"] and os.path.exists(inv["pdf_path"]):
                with open(inv["pdf_path"], "rb") as f:
                    c4.download_button("⬇️ PDF", f, file_name=os.path.basename(inv["pdf_path"]),
                                        mime="application/pdf", key=f"dl_{inv['id']}")
