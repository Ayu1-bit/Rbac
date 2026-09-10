"""
Shared PDF generation — used by both the Invoicing page and the POS page so there is
exactly one place that builds a tax invoice / receipt, not two diverging copies.
"""
import os
from datetime import date

from utils.db import get_setting

INVOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "invoices")
os.makedirs(INVOICE_DIR, exist_ok=True)


def build_invoice_pdf(invoice_number, order, customer, items, subtotal, gst_amount, total):
    """
    invoice_number: str, e.g. "INV-0007"
    order: dict-like row from `orders` (needs at least 'order_number')
    customer: dict-like row from `customers`, or None for walk-in
    items: list of {"name": str, "qty": int, "price": float}
    """
    from fpdf import FPDF

    company = get_setting("company_name", "Jewellery Store")
    gstin = get_setting("gst_number", "")
    address = get_setting("address", "")
    phone = get_setting("phone", "")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, company, ln=True)
    pdf.set_font("Helvetica", "", 10)
    if address:
        pdf.cell(0, 6, address, ln=True)
    if gstin:
        pdf.cell(0, 6, f"GSTIN: {gstin}", ln=True)
    if phone:
        pdf.cell(0, 6, f"Phone: {phone}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"TAX INVOICE  #{invoice_number}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Date: {date.today().isoformat()}", ln=True)
    pdf.cell(0, 6, f"Order #: {order['order_number']}", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Bill To:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, customer["name"] if customer else "Walk-in Customer", ln=True)
    if customer:
        if customer.get("phone"):
            pdf.cell(0, 6, f"Phone: {customer['phone']}", ln=True)
        if customer.get("address"):
            pdf.cell(0, 6, f"Address: {customer['address']}, {customer.get('city', '')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    col_widths = [70, 20, 30, 30, 30]
    headers = ["Item", "Qty", "Unit Price", "Line Total", ""]
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    for it in items:
        line_total = it["qty"] * it["price"]
        pdf.cell(col_widths[0], 8, str(it["name"])[:38], border=1)
        pdf.cell(col_widths[1], 8, str(it["qty"]), border=1, align="C")
        pdf.cell(col_widths[2], 8, f"{it['price']:.2f}", border=1, align="R")
        pdf.cell(col_widths[3], 8, f"{line_total:.2f}", border=1, align="R")
        pdf.cell(col_widths[4], 8, "", border=1)
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(150, 7, "Subtotal", align="R")
    pdf.cell(30, 7, f"{subtotal:.2f}", align="R", ln=True)
    pdf.cell(150, 7, "GST", align="R")
    pdf.cell(30, 7, f"{gst_amount:.2f}", align="R", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(150, 8, "Total", align="R")
    pdf.cell(30, 8, f"{total:.2f}", align="R", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Thank you for your business!", ln=True)

    path = os.path.join(INVOICE_DIR, f"{invoice_number}.pdf")
    pdf.output(path)
    return path
