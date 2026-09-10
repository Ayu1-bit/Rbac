import streamlit as st
import pandas as pd
from datetime import date

from utils.db import init_db, run_query, next_number, get_setting
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box, current_user
from utils.pdf import build_invoice_pdf

st.set_page_config(page_title="POS · Jewellery ERP", page_icon="🛒", layout="wide")
init_db()
require_role("admin", "manager", "sales")
render_sidebar_user_box()
st.title("🛒 Point of Sale")

if "pos_cart" not in st.session_state:
    st.session_state.pos_cart = []
if "pos_customer_id" not in st.session_state:
    st.session_state.pos_customer_id = None

col_shop, col_cart = st.columns([3, 2])

# ---------------------------------------------------------------- LEFT: product search / scan
with col_shop:
    st.subheader("🔍 Find a product")
    search = st.text_input("Scan barcode, or search by SKU / name", key="pos_search")

    products = run_query("SELECT * FROM products WHERE status='active' ORDER BY name", fetch=True)

    if search:
        s = search.strip().lower()
        matches = [
            p for p in products
            if s in (p["sku"] or "").lower()
            or s in (p["name"] or "").lower()
            or s == (p["barcode"] or "").lower()
        ]
    else:
        matches = products[:20]

    if not matches:
        st.info("No matching products. Try a different search, or add the product on the Products page.")
    else:
        for p in matches:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{p['name']}**  \n`{p['sku']}` · {currency(p['selling_price'])}")
                c1.caption(f"Stock: {p['stock_qty']}")
                qty_key = f"qty_{p['id']}"
                qty = c2.number_input("Qty", min_value=1, step=1, value=1, key=qty_key, label_visibility="collapsed")
                add_disabled = p["stock_qty"] <= 0
                if c3.button("➕ Add", key=f"add_{p['id']}", disabled=add_disabled, use_container_width=True):
                    existing = next((i for i in st.session_state.pos_cart if i["product_id"] == p["id"]), None)
                    if existing:
                        existing["qty"] += qty
                    else:
                        st.session_state.pos_cart.append({
                            "product_id": p["id"], "sku": p["sku"], "name": p["name"],
                            "qty": qty, "price": p["selling_price"], "stock_available": p["stock_qty"],
                        })
                    st.rerun()
                if add_disabled:
                    c3.caption("Out of stock")

# ---------------------------------------------------------------- RIGHT: cart + checkout
with col_cart:
    st.subheader("🧺 Cart")

    if not st.session_state.pos_cart:
        st.info("Cart is empty — add products from the left.")
    else:
        for idx, item in enumerate(st.session_state.pos_cart):
            with st.container(border=True):
                cc1, cc2, cc3 = st.columns([3, 1, 1])
                cc1.markdown(f"**{item['name']}**  \n`{item['sku']}` · {currency(item['price'])} each")
                new_qty = cc2.number_input(
                    "Qty", min_value=1, max_value=max(item.get("stock_available", 999), 1),
                    step=1, value=item["qty"], key=f"cart_qty_{idx}", label_visibility="collapsed",
                )
                item["qty"] = new_qty
                if cc3.button("🗑️", key=f"remove_{idx}"):
                    st.session_state.pos_cart.pop(idx)
                    st.rerun()

        if st.button("🧹 Clear cart"):
            st.session_state.pos_cart = []
            st.rerun()

        st.divider()

        # ---- customer ----
        st.markdown("**Customer**")
        customers = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
        cust_labels = ["🚶 Walk-in (no customer record)"] + [
            f"{c['name']} ({c['phone'] or c['email'] or '—'})" for c in customers
        ]
        cust_lookup = {f"{c['name']} ({c['phone'] or c['email'] or '—'})": c["id"] for c in customers}
        cust_choice = st.selectbox("Customer", cust_labels, label_visibility="collapsed")
        selected_customer_id = cust_lookup.get(cust_choice)

        with st.expander("➕ Quick-add a new customer"):
            with st.form("pos_new_customer", clear_on_submit=True):
                qn_name = st.text_input("Name")
                qn_phone = st.text_input("Phone")
                if st.form_submit_button("Add customer"):
                    if qn_name:
                        new_id = run_query(
                            "INSERT INTO customers (name, phone, created_at) VALUES (?,?,datetime('now'))",
                            (qn_name, qn_phone),
                        )
                        st.success(f"Added {qn_name} — select them above.")
                        st.rerun()
                    else:
                        st.error("Name is required.")

        st.divider()

        # ---- totals ----
        cart_df = pd.DataFrame(st.session_state.pos_cart)
        cart_df["line_total"] = cart_df["qty"] * cart_df["price"]
        subtotal = cart_df["line_total"].sum()

        discount = st.number_input("Discount (₹)", min_value=0.0, step=50.0, value=0.0)
        gst_rate = float(get_setting("gst_rate", "3") or 3)
        gst_amount = round((subtotal - discount) * (gst_rate / 100.0), 2)
        total = subtotal - discount + gst_amount

        st.metric("Subtotal", currency(subtotal))
        st.metric(f"GST ({gst_rate:.1f}%)", currency(gst_amount))
        st.metric("**Total Due**", currency(total))

        st.divider()

        # ---- payment ----
        st.markdown("**Payment**")
        payment_method = st.radio("Method", ["Cash", "Card", "UPI", "Split"], horizontal=True)
        tendered = None
        change_due = None
        if payment_method == "Cash":
            tendered = st.number_input("Amount tendered (₹)", min_value=0.0, step=50.0, value=float(round(total)))
            change_due = max(tendered - total, 0)
            st.caption(f"Change due: {currency(change_due)}")

        if st.button("✅ Complete Sale", type="primary", use_container_width=True):
            order_number = next_number("ORD", "orders", "order_number")
            user = current_user()
            oid = run_query(
                """INSERT INTO orders
                   (order_number, customer_id, order_date, status, payment_status, subtotal,
                    tax_amount, discount, total_amount, created_by_user_id, channel, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    order_number, selected_customer_id, date.today().isoformat(),
                    "delivered", "paid", subtotal, gst_amount, discount, total,
                    user["id"], "pos", f"POS sale — {payment_method}",
                ),
            )
            for item in st.session_state.pos_cart:
                run_query(
                    "INSERT INTO order_items (order_id, product_id, qty, price) VALUES (?,?,?,?)",
                    (oid, item["product_id"], item["qty"], item["price"]),
                )
                run_query(
                    "UPDATE products SET stock_qty = MAX(stock_qty - ?, 0) WHERE id=?",
                    (item["qty"], item["product_id"]),
                )

            # Generate the receipt immediately — reuses the exact same PDF builder as Invoicing.
            order_row = run_query("SELECT * FROM orders WHERE id=?", (oid,), fetchone=True)
            customer_row = (
                run_query("SELECT * FROM customers WHERE id=?", (selected_customer_id,), fetchone=True)
                if selected_customer_id else None
            )
            receipt_items = [{"name": i["name"], "qty": i["qty"], "price": i["price"]} for i in st.session_state.pos_cart]
            invoice_number = next_number("INV", "invoices", "invoice_number")
            pdf_path = build_invoice_pdf(invoice_number, order_row, customer_row, receipt_items, subtotal, gst_amount, total)
            run_query(
                """INSERT INTO invoices (invoice_number, order_id, invoice_date, subtotal, gst_amount, total, pdf_path)
                   VALUES (?,?,?,?,?,?,?)""",
                (invoice_number, oid, date.today().isoformat(), subtotal, gst_amount, total, pdf_path),
            )

            st.session_state.pos_cart = []
            st.success(f"✅ Sale complete — Order {order_number}, Invoice {invoice_number}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download Receipt", f, file_name=f"{invoice_number}.pdf",
                    mime="application/pdf", key="pos_receipt_dl",
                )
