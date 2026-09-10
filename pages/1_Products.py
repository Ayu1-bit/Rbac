import streamlit as st
import pandas as pd
from datetime import datetime

from utils.db import init_db, run_query, get_setting
from utils.helpers import currency, calc_product_price, latest_rate, stock_status
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Products · Jewellery ERP", page_icon="💍", layout="wide")
init_db()
require_role("admin", "manager")
render_sidebar_user_box()
st.title("💍 Product & Inventory Management")

tab_list, tab_add, tab_edit = st.tabs(["📋 Inventory List", "➕ Add Product", "✏️ Edit / Delete"])

CATEGORIES = ["Ring", "Necklace", "Earring", "Bracelet", "Bangle", "Pendant", "Chain", "Anklet", "Nose Pin", "Other"]
METALS = ["Gold", "Silver", "Platinum"]
PURITY_MAP = {"Gold": ["24K", "22K", "18K", "14K"], "Silver": ["999", "925"], "Platinum": ["950", "900"]}
MAKING_TYPES = ["per_gram", "percentage", "fixed"]

# ---------------- LIST ----------------
with tab_list:
    products = run_query("SELECT * FROM products ORDER BY created_at DESC", fetch=True)
    if not products:
        st.info("No products yet — add your first jewellery item in the **Add Product** tab.")
    else:
        colf1, colf2, colf3, colf4 = st.columns(4)
        with colf1:
            f_cat = st.selectbox("Category", ["All"] + CATEGORIES)
        with colf2:
            f_metal = st.selectbox("Metal", ["All"] + METALS)
        with colf3:
            f_status = st.selectbox("Status", ["All", "active", "inactive"])
        with colf4:
            f_search = st.text_input("Search name/SKU")

        df = pd.DataFrame(products)
        if f_cat != "All":
            df = df[df["category"] == f_cat]
        if f_metal != "All":
            df = df[df["metal_type"] == f_metal]
        if f_status != "All":
            df = df[df["status"] == f_status]
        if f_search:
            mask = df["name"].str.contains(f_search, case=False, na=False) | df["sku"].str.contains(f_search, case=False, na=False)
            df = df[mask]

        df["Stock"] = df.apply(lambda r: stock_status(r["stock_qty"], r["reorder_level"]), axis=1)
        show = df[["sku", "name", "category", "metal_type", "purity", "net_weight",
                   "selling_price", "stock_qty", "Stock", "shopify_product_id"]].copy()
        show.columns = ["SKU", "Name", "Category", "Metal", "Purity", "Net Wt (g)",
                        "Selling Price", "Qty", "Stock Status", "Shopify ID"]
        show["Selling Price"] = show["Selling Price"].apply(currency)
        st.dataframe(show, hide_index=True, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total SKUs shown", len(df))
        c2.metric("Total Stock Qty", int(df["stock_qty"].sum()) if len(df) else 0)
        c3.metric("Inventory Value (selling)", currency((df["selling_price"] * df["stock_qty"]).sum() if len(df) else 0))

        st.download_button("⬇️ Export CSV", show.to_csv(index=False).encode("utf-8"),
                            "inventory_export.csv", "text/csv")

# ---------------- ADD ----------------
with tab_add:
    st.subheader("Add a new jewellery item")
    use_calc = st.checkbox("Auto-calculate selling price from live metal rate", value=True)

    with st.form("add_product_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            sku = st.text_input("SKU *", placeholder="RG-0001")
            name = st.text_input("Product Name *", placeholder="Solitaire Diamond Ring")
            category = st.selectbox("Category", CATEGORIES)
            metal_type = st.selectbox("Metal Type", METALS)
            purity = st.selectbox("Purity", PURITY_MAP[metal_type])
        with c2:
            gross_weight = st.number_input("Gross Weight (g)", min_value=0.0, step=0.01)
            stone_weight = st.number_input("Stone Weight (g)", min_value=0.0, step=0.01)
            net_weight = st.number_input("Net Metal Weight (g) *", min_value=0.0, step=0.01,
                                          help="Gross weight minus stone weight")
            stone_type = st.text_input("Stone Type", placeholder="Diamond / Ruby / None")
            stone_cost = st.number_input("Stone Cost (₹)", min_value=0.0, step=100.0)
        with c3:
            making_charge_type = st.selectbox("Making Charge Type", MAKING_TYPES)
            making_charge_value = st.number_input(
                "Making Charge Value", min_value=0.0, step=1.0,
                help="Per gram (₹), percentage of metal value (%), or fixed amount (₹)")
            stock_qty = st.number_input("Opening Stock Qty", min_value=0, step=1, value=1)
            reorder_level = st.number_input("Reorder Level", min_value=0, step=1, value=2)
            hsn_code = st.text_input("HSN Code", value="7113")

        barcode = st.text_input("Barcode / Shopify SKU (optional)")
        image_url = st.text_input("Image URL (optional)")

        rate = latest_rate(metal_type, purity) if net_weight else 0.0
        if use_calc and net_weight > 0:
            pricing = calc_product_price(net_weight, rate, making_charge_type, making_charge_value, stone_cost)
            st.info(
                f"**Live rate:** {currency(rate)}/g for {metal_type} {purity}  \n"
                f"Metal Value: {currency(pricing['metal_value'])} · "
                f"Making: {currency(pricing['making_charge'])} · "
                f"Stone: {currency(pricing['stone_cost'])} · "
                f"GST ({pricing['gst_rate']}%): {currency(pricing['gst_amount'])}  \n"
                f"**Suggested Selling Price: {currency(pricing['total'])}**"
            )
            default_price = pricing["total"]
            default_cost = pricing["subtotal"]
        else:
            default_price = 0.0
            default_cost = 0.0

        cprice1, cprice2 = st.columns(2)
        with cprice1:
            cost_price = st.number_input("Cost Price (₹)", min_value=0.0, step=100.0, value=float(round(default_cost, 2)))
        with cprice2:
            selling_price = st.number_input("Selling Price (₹) *", min_value=0.0, step=100.0, value=float(round(default_price, 2)))

        submitted = st.form_submit_button("💾 Save Product", type="primary")
        if submitted:
            if not sku or not name or net_weight <= 0 or selling_price <= 0:
                st.error("Please fill required fields: SKU, Name, Net Weight, Selling Price.")
            else:
                existing = run_query("SELECT id FROM products WHERE sku=?", (sku,), fetchone=True)
                if existing:
                    st.error(f"SKU '{sku}' already exists. Use a unique SKU.")
                else:
                    now = datetime.now().isoformat()
                    run_query("""INSERT INTO products
                        (sku, name, category, metal_type, purity, gross_weight, net_weight,
                         stone_weight, stone_type, stone_cost, making_charge_type, making_charge_value,
                         cost_price, selling_price, stock_qty, reorder_level, hsn_code, barcode,
                         image_url, status, created_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (sku, name, category, metal_type, purity, gross_weight, net_weight,
                         stone_weight, stone_type, stone_cost, making_charge_type, making_charge_value,
                         cost_price, selling_price, stock_qty, reorder_level, hsn_code, barcode,
                         image_url, "active", now, now))
                    st.success(f"✅ Product '{name}' ({sku}) added successfully!")
                    st.rerun()

# ---------------- EDIT/DELETE ----------------
with tab_edit:
    products = run_query("SELECT * FROM products ORDER BY name", fetch=True)
    if not products:
        st.info("No products to edit yet.")
    else:
        options = {f"{p['sku']} — {p['name']}": p["id"] for p in products}
        choice = st.selectbox("Select product", list(options.keys()))
        pid = options[choice]
        p = run_query("SELECT * FROM products WHERE id=?", (pid,), fetchone=True)

        with st.form("edit_product_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("Name", value=p["name"])
                category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(p["category"]) if p["category"] in CATEGORIES else 0)
                metal_type = st.selectbox("Metal", METALS, index=METALS.index(p["metal_type"]) if p["metal_type"] in METALS else 0)
                purity = st.text_input("Purity", value=p["purity"])
            with c2:
                net_weight = st.number_input("Net Weight (g)", value=float(p["net_weight"]), min_value=0.0, step=0.01)
                stock_qty = st.number_input("Stock Qty", value=int(p["stock_qty"]), min_value=0, step=1)
                reorder_level = st.number_input("Reorder Level", value=int(p["reorder_level"]), min_value=0, step=1)
                status = st.selectbox("Status", ["active", "inactive"], index=0 if p["status"] == "active" else 1)
            with c3:
                cost_price = st.number_input("Cost Price", value=float(p["cost_price"]), min_value=0.0, step=100.0)
                selling_price = st.number_input("Selling Price", value=float(p["selling_price"]), min_value=0.0, step=100.0)
                shopify_product_id = st.text_input("Shopify Product ID", value=p["shopify_product_id"] or "")

            csub1, csub2 = st.columns(2)
            update_btn = csub1.form_submit_button("💾 Update Product", type="primary")
            delete_btn = csub2.form_submit_button("🗑️ Delete Product")

            if update_btn:
                run_query("""UPDATE products SET name=?, category=?, metal_type=?, purity=?, net_weight=?,
                             stock_qty=?, reorder_level=?, status=?, cost_price=?, selling_price=?,
                             shopify_product_id=?, updated_at=? WHERE id=?""",
                          (name, category, metal_type, purity, net_weight, stock_qty, reorder_level,
                           status, cost_price, selling_price, shopify_product_id, datetime.now().isoformat(), pid))
                st.success("Product updated ✅")
                st.rerun()

            if delete_btn:
                run_query("DELETE FROM products WHERE id=?", (pid,))
                st.success("Product deleted.")
                st.rerun()
