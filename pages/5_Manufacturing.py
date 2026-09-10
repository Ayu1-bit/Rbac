import streamlit as st
import pandas as pd
from datetime import datetime, date

from utils.db import init_db, run_query, next_number
from utils.helpers import currency
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Manufacturing · Jewellery ERP", page_icon="🛠️", layout="wide")
init_db()
require_role("admin", "manager", "production")
render_sidebar_user_box()
st.title("🛠️ Manufacturing & Karigar Job Tracking")
st.caption("Track raw-metal issued to artisans (karigars), wastage, labour charges, and finished-goods receipt.")

tab_list, tab_new = st.tabs(["📋 Jobs", "➕ New Job"])

STATUSES = ["assigned", "in_progress", "completed", "delayed"]

with tab_list:
    jobs = run_query("""
        SELECT mj.*, p.name as product_name, p.sku FROM manufacturing_jobs mj
        LEFT JOIN products p ON mj.product_id = p.id ORDER BY mj.start_date DESC
    """, fetch=True)
    if not jobs:
        st.info("No manufacturing jobs yet.")
    else:
        f_status = st.selectbox("Filter by status", ["All"] + STATUSES)
        df = pd.DataFrame(jobs)
        if f_status != "All":
            df = df[df["status"] == f_status]

        df["wastage_pct"] = df.apply(
            lambda r: round(((r["given_weight"] - r["received_weight"]) / r["given_weight"] * 100), 2)
            if r["given_weight"] else 0, axis=1)

        show = df[["job_number", "karigar_name", "product_name", "given_weight",
                   "received_weight", "wastage_pct", "labour_charge", "status", "expected_date"]].copy()
        show.columns = ["Job #", "Karigar", "Product", "Given Wt (g)", "Received Wt (g)",
                        "Wastage %", "Labour Charge", "Status", "Expected Date"]
        show["Labour Charge"] = show["Labour Charge"].apply(currency)
        st.dataframe(show, hide_index=True, use_container_width=True)

        st.divider()
        opts = {j["job_number"]: j["id"] for j in jobs}
        sel = st.selectbox("Update a job", list(opts.keys()))
        jid = opts[sel]
        current = run_query("SELECT * FROM manufacturing_jobs WHERE id=?", (jid,), fetchone=True)

        c1, c2, c3 = st.columns(3)
        new_status = c1.selectbox("Status", STATUSES, index=STATUSES.index(current["status"]) if current["status"] in STATUSES else 0)
        received_weight = c2.number_input("Received Weight (g)", min_value=0.0, step=0.01, value=float(current["received_weight"] or 0))
        completed_date = c3.date_input("Completed Date", value=date.today())

        if st.button("💾 Update Job", type="primary"):
            wastage = max((current["given_weight"] or 0) - received_weight, 0)
            comp_date = completed_date.isoformat() if new_status == "completed" else None
            run_query("""UPDATE manufacturing_jobs SET status=?, received_weight=?, wastage=?, completed_date=?
                         WHERE id=?""", (new_status, received_weight, wastage, comp_date, jid))
            st.success("Job updated ✅")
            st.rerun()

with tab_new:
    products = run_query("SELECT * FROM products ORDER BY name", fetch=True)
    with st.form("add_job", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            karigar_name = st.text_input("Karigar / Artisan Name *")
            description = st.text_input("Job Description", placeholder="Custom bangle set, engraving, resizing...")
            product_opts = {"— None (custom job) —": None}
            product_opts.update({f"{p['sku']} — {p['name']}": p["id"] for p in products})
            product_choice = st.selectbox("Linked Product (optional)", list(product_opts.keys()))
        with c2:
            given_weight = st.number_input("Metal Weight Given (g) *", min_value=0.0, step=0.01)
            labour_charge = st.number_input("Labour Charge (₹)", min_value=0.0, step=100.0)
            start_date_input = st.date_input("Start Date", value=date.today())
            expected_date_input = st.date_input("Expected Completion Date")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("💾 Create Job", type="primary")
        if submitted:
            if not karigar_name or given_weight <= 0:
                st.error("Karigar name and metal weight given are required.")
            else:
                job_number = next_number("JOB", "manufacturing_jobs", "job_number")
                run_query("""INSERT INTO manufacturing_jobs
                    (job_number, karigar_name, description, product_id, given_weight, received_weight,
                     wastage, labour_charge, status, start_date, expected_date, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (job_number, karigar_name, description, product_opts[product_choice], given_weight,
                     0, 0, labour_charge, "assigned", start_date_input.isoformat(),
                     expected_date_input.isoformat(), notes))
                st.success(f"✅ Job {job_number} created and assigned to {karigar_name}!")
                st.rerun()
