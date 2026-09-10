import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from utils.db import init_db, get_setting
from utils.shopify_graphql import fetch_products_full
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Product Explorer · Jewellery ERP", page_icon="🖼️", layout="wide")
init_db()
require_role("admin", "manager")
render_sidebar_user_box()
st.title("🖼️ Shopify Product Explorer")
st.caption("Live view straight from your Shopify store — images, every variant, and any 3D models attached to a product.")

if not get_setting("shopify_access_token"):
    st.warning("Not connected to Shopify yet. Go to **Shopify Sync** to connect your store first.")
    st.stop()

c1, c2 = st.columns([1, 3])
count = c1.slider("Products to load", 5, 100, 20)
if c1.button("🔄 Refresh from Shopify", type="primary"):
    st.session_state.pop("product_explorer_data", None)

if "product_explorer_data" not in st.session_state:
    try:
        with st.spinner("Fetching products from Shopify..."):
            st.session_state.product_explorer_data = fetch_products_full(first=count)
    except Exception as e:
        st.error(f"Could not fetch products: {e}")
        st.stop()

data = st.session_state.product_explorer_data
edges = data.get("edges", [])

search = c2.text_input("Filter by title / vendor / tag")

MODEL_VIEWER_SCRIPT = '<script type="module" src="https://cdnjs.cloudflare.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>'

if not edges:
    st.info("No products found in your store yet.")
else:
    for edge in edges:
        p = edge["node"]
        title = p["title"]
        vendor = p.get("vendor") or ""
        tags = p.get("tags") or []
        if search:
            haystack = f"{title} {vendor} {' '.join(tags)}".lower()
            if search.lower() not in haystack:
                continue

        with st.container(border=True):
            top1, top2 = st.columns([3, 1])
            with top1:
                st.subheader(title)
                st.caption(f"Vendor: {vendor or '—'} · Type: {p.get('productType') or '—'} · "
                           f"Status: {p.get('status')} · Total inventory: {p.get('totalInventory')}")
                if tags:
                    st.write(" ".join([f"`{t}`" for t in tags]))
            with top2:
                if p.get("onlineStoreUrl"):
                    st.link_button("View on storefront ↗", p["onlineStoreUrl"])

            img_tab, media3d_tab, variants_tab, desc_tab = st.tabs(
                ["📷 Images", "🧊 3D / Video", "📊 Variants", "📝 Description"]
            )

            with img_tab:
                images = [n["node"] for n in p.get("images", {}).get("edges", [])]
                if images:
                    cols = st.columns(min(len(images), 5))
                    for i, img in enumerate(images):
                        with cols[i % 5]:
                            st.image(img["url"], caption=img.get("altText") or "", use_container_width=True)
                else:
                    st.caption("No images uploaded for this product.")

            with media3d_tab:
                media_nodes = [n["node"] for n in p.get("media", {}).get("edges", [])]
                models = [m for m in media_nodes if m.get("mediaContentType") == "MODEL_3D"]
                videos = [m for m in media_nodes if m.get("mediaContentType") == "VIDEO"]
                if models:
                    for m in models:
                        sources = m.get("sources", [])
                        glb = next((s["url"] for s in sources if s.get("format") in ("glb", "gltf")), None)
                        usdz = next((s["url"] for s in sources if s.get("format") == "usdz"), None)
                        if glb:
                            html = f"""
                            {MODEL_VIEWER_SCRIPT}
                            <model-viewer src="{glb}" {"ios-src='" + usdz + "'" if usdz else ""}
                                alt="{m.get('alt') or title}" auto-rotate camera-controls
                                style="width:100%;height:420px;background:#f5f5f5;border-radius:8px;">
                            </model-viewer>
                            """
                            components.html(html, height=440)
                        else:
                            st.caption("3D model attached but no viewable GLB/glTF source found.")
                if videos:
                    for v in videos:
                        vsrc = next((s["url"] for s in v.get("sources", [])), None)
                        if vsrc:
                            st.video(vsrc)
                if not models and not videos:
                    st.caption("No 3D models or videos attached to this product.")

            with variants_tab:
                variants = [n["node"] for n in p.get("variants", {}).get("edges", [])]
                if variants:
                    rows = []
                    for v in variants:
                        opts = ", ".join(f"{o['name']}: {o['value']}" for o in v.get("selectedOptions", []))
                        rows.append({
                            "Variant": v.get("title"), "Options": opts, "SKU": v.get("sku"),
                            "Price": v.get("price"), "Compare-at": v.get("compareAtPrice"),
                            "Inventory": v.get("inventoryQuantity"),
                        })
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                else:
                    st.caption("No variants found.")

            with desc_tab:
                html_desc = p.get("descriptionHtml") or "<i>No description.</i>"
                st.markdown(html_desc, unsafe_allow_html=True)

    page_info = data.get("pageInfo", {})
    if page_info.get("hasNextPage"):
        if st.button("⬇️ Load more products"):
            more = fetch_products_full(first=count, after=page_info.get("endCursor"))
            st.session_state.product_explorer_data["edges"].extend(more["edges"])
            st.session_state.product_explorer_data["pageInfo"] = more["pageInfo"]
            st.rerun()
