import streamlit as st
import pandas as pd
from datetime import datetime, date

from utils.db import init_db, run_query, next_number
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Orders · Jewellery ERP", page_icon="📦", layout="wide")
init_db()
require_role("admin", "manager", "sales")
render_sidebar_user_box()
st.title("📦 Order Management")

STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"]
PAY_STATUSES = ["unpaid", "partial", "paid", "refunded"]

tab_list, tab_new = st.tabs(["📋 All Orders", "➕ New Manual Order"])

with tab_list:
    orders = run_query("""
        SELECT o.*, c.name as customer_name FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        ORDER BY o.order_date DESC
    """, fetch=True)

    if not orders:
        st.info("No orders yet. Create one manually, or sync orders from the **Shopify Sync** page.")
    else:
        c1, c2 = st.columns(2)
        f_status = c1.selectbox("Filter by status", ["All"] + STATUSES)
        f_search = c2.text_input("Search order # / customer")

        df = pd.DataFrame(orders)
        if f_status != "All":
            df = df[df["status"] == f_status]
        if f_search:
            mask = df["order_number"].str.contains(f_search, case=False, na=False) | \
                   df["customer_name"].fillna("").str.contains(f_search, case=False, na=False)
            df = df[mask]

        show = df[["order_number", "customer_name", "order_date", "status", "payment_status", "total_amount"]].copy()
        show.columns = ["Order #", "Customer", "Date", "Status", "Payment", "Total"]
        show["Total"] = show["Total"].apply(currency)
        st.dataframe(show, hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Update Order Status")
        order_opts = {o["order_number"]: o["id"] for o in orders}
        sel = st.selectbox("Select order", list(order_opts.keys()))
        oid = order_opts[sel]
        current = run_query("SELECT * FROM orders WHERE id=?", (oid,), fetchone=True)

        cu1, cu2, cu3 = st.columns(3)
        new_status = cu1.selectbox("Status", STATUSES, index=STATUSES.index(current["status"]) if current["status"] in STATUSES else 0)
        new_pay = cu2.selectbox("Payment Status", PAY_STATUSES, index=PAY_STATUSES.index(current["payment_status"]) if current["payment_status"] in PAY_STATUSES else 0)
        if cu3.button("💾 Update", type="primary"):
            run_query("UPDATE orders SET status=?, payment_status=? WHERE id=?", (new_status, new_pay, oid))
            st.success("Order updated ✅")
            st.rerun()

        with st.expander("View order items"):
            items = run_query("""
                SELECT oi.*, p.name as product_name, p.sku FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id=?
            """, (oid,), fetch=True)
            if items:
                idf = pd.DataFrame(items)[["sku", "product_name", "qty", "price"]]
                idf.columns = ["SKU", "Product", "Qty", "Price"]
                idf["Price"] = idf["Price"].apply(currency)
                st.dataframe(idf, hide_index=True, use_container_width=True)
            else:
                st.caption("No line items recorded for this order.")

with tab_new:
    st.subheader("Create a manual order")
    customers = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
    products = run_query("SELECT * FROM products WHERE status='active' ORDER BY name", fetch=True)

    if not customers:
        st.warning("Add a customer first on the **Customers** page.")
    elif not products:
        st.warning("Add a product first on the **Products** page.")
    else:
        cust_opts = {f"{c['name']} ({c['phone'] or c['email'] or ''})": c["id"] for c in customers}
        cust_choice = st.selectbox("Customer", list(cust_opts.keys()))

        st.markdown("**Line items**")
        if "order_items_cart" not in st.session_state:
            st.session_state.order_items_cart = []

        prod_opts = {f"{p['sku']} — {p['name']} ({currency(p['selling_price'])}, stock {p['stock_qty']})": p for p in products}
        pc1, pc2, pc3 = st.columns([3, 1, 1])
        prod_choice = pc1.selectbox("Product", list(prod_opts.keys()), key="prod_choice")
        qty = pc2.number_input("Qty", min_value=1, step=1, value=1, key="qty_choice")
        if pc3.button("➕ Add to order"):
            prod = prod_opts[prod_choice]
            st.session_state.order_items_cart.append({
                "product_id": prod["id"], "sku": prod["sku"], "name": prod["name"],
                "qty": qty, "price": prod["selling_price"]
            })

        if st.session_state.order_items_cart:
            cart_df = pd.DataFrame(st.session_state.order_items_cart)
            cart_df["line_total"] = cart_df["qty"] * cart_df["price"]
            show_cart = cart_df[["sku", "name", "qty", "price", "line_total"]].copy()
            show_cart.columns = ["SKU", "Product", "Qty", "Price", "Line Total"]
            st.dataframe(show_cart, hide_index=True, use_container_width=True)
            subtotal = cart_df["line_total"].sum()

            if st.button("🧹 Clear cart"):
                st.session_state.order_items_cart = []
                st.rerun()

            discount = st.number_input("Discount (₹)", min_value=0.0, step=100.0, value=0.0)
            tax_amount = st.number_input("Tax / GST (₹)", min_value=0.0, step=10.0, value=round(subtotal * 0.03, 2))
            total = subtotal - discount + tax_amount
            st.metric("Order Total", currency(total))

            order_date_input = st.date_input("Order Date", value=date.today())

            if st.button("✅ Confirm & Save Order", type="primary"):
                order_number = next_number("ORD", "orders", "order_number")
                cust_id = cust_opts[cust_choice]
                oid = run_query("""INSERT INTO orders
                    (order_number, customer_id, order_date, status, payment_status, subtotal, tax_amount,
                     discount, total_amount) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (order_number, cust_id, order_date_input.isoformat(), "pending", "unpaid",
                     subtotal, tax_amount, discount, total))
                for item in st.session_state.order_items_cart:
                    run_query("""INSERT INTO order_items (order_id, product_id, qty, price)
                                 VALUES (?,?,?,?)""", (oid, item["product_id"], item["qty"], item["price"]))
                    run_query("UPDATE products SET stock_qty = MAX(stock_qty - ?, 0) WHERE id=?",
                              (item["qty"], item["product_id"]))
                st.session_state.order_items_cart = []
                st.success(f"✅ Order {order_number} created!")
                st.rerun()
        else:
            st.caption("Add at least one product to the cart to create an order.")
