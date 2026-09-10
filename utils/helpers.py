"""
Business-logic helpers: jewellery pricing, GST, formatting.
"""
from utils.db import get_setting


def currency(amount):
    sym = get_setting("currency_symbol", "₹")
    try:
        return f"{sym}{amount:,.2f}"
    except Exception:
        return f"{sym}0.00"


def calc_making_charge(metal_value, weight, making_type, making_value):
    """making_type: 'per_gram' | 'percentage' | 'fixed'"""
    if making_type == "per_gram":
        return weight * making_value
    if making_type == "percentage":
        return metal_value * (making_value / 100.0)
    if making_type == "fixed":
        return making_value
    return 0.0


def calc_product_price(net_weight, metal_rate_per_gram, making_type, making_value,
                        stone_cost=0.0, gst_rate=None):
    """
    Core jewellery pricing formula:
      Metal Value = Net Weight * Rate/gram
      Making Charges = per_gram / percentage-of-metal-value / fixed
      Subtotal = Metal Value + Making Charges + Stone Cost
      GST = Subtotal * gst_rate%
      Total = Subtotal + GST
    """
    if gst_rate is None:
        gst_rate = float(get_setting("gst_rate", "3") or 3)

    metal_value = net_weight * metal_rate_per_gram
    making_charge = calc_making_charge(metal_value, net_weight, making_type, making_value)
    subtotal = metal_value + making_charge + stone_cost
    gst_amount = subtotal * (gst_rate / 100.0)
    total = subtotal + gst_amount

    return {
        "metal_value": round(metal_value, 2),
        "making_charge": round(making_charge, 2),
        "stone_cost": round(stone_cost, 2),
        "subtotal": round(subtotal, 2),
        "gst_rate": gst_rate,
        "gst_amount": round(gst_amount, 2),
        "total": round(total, 2),
    }


def latest_rate(metal_type, purity):
    from utils.db import run_query
    row = run_query(
        "SELECT rate_per_gram FROM metal_rates WHERE metal_type=? AND purity=? "
        "ORDER BY rate_date DESC, id DESC LIMIT 1",
        (metal_type, purity), fetchone=True
    )
    return row["rate_per_gram"] if row else 0.0


def stock_status(qty, reorder_level):
    if qty <= 0:
        return "🔴 Out of Stock"
    if qty <= reorder_level:
        return "🟡 Low Stock"
    return "🟢 In Stock"
