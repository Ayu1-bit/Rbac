import streamlit as st
import streamlit.components.v1 as components

from utils.db import init_db, get_setting
from utils.shopify_graphql import fetch_files_full
from utils.auth import require_role, render_sidebar_user_box

st.set_page_config(page_title="Files Library · Jewellery ERP", page_icon="🗂️", layout="wide")
init_db()
require_role("admin", "manager")
render_sidebar_user_box()
st.title("🗂️ Shopify Files Library")
st.caption("Every file in your store's Content → Files library: images, videos, 3D models, and generic uploads (PDFs, certs, etc.)")

if not get_setting("shopify_access_token"):
    st.warning("Not connected to Shopify yet. Go to **Shopify Sync** to connect your store first.")
    st.stop()

count = st.slider("Files to load", 10, 150, 40)
if st.button("🔄 Refresh from Shopify", type="primary"):
    st.session_state.pop("files_library_data", None)

if "files_library_data" not in st.session_state:
    try:
        with st.spinner("Fetching files from Shopify..."):
            st.session_state.files_library_data = fetch_files_full(first=count)
    except Exception as e:
        st.error(f"Could not fetch files: {e}")
        st.stop()

data = st.session_state.files_library_data
edges = data.get("edges", [])
MODEL_VIEWER_SCRIPT = '<script type="module" src="https://cdnjs.cloudflare.com/ajax/libs/model-viewer/3.5.0/model-viewer.min.js"></script>'

if not edges:
    st.info("No files found in your store's Files library.")
else:
    cols = st.columns(3)
    for i, edge in enumerate(edges):
        f = edge["node"]
        with cols[i % 3]:
            with st.container(border=True):
                if f.get("image"):
                    st.image(f["image"]["url"], use_container_width=True)
                elif f.get("sources"):
                    src = f["sources"][0]
                    fmt = src.get("format", "")
                    if fmt in ("glb", "gltf"):
                        html = f"""{MODEL_VIEWER_SCRIPT}
                        <model-viewer src="{src['url']}" auto-rotate camera-controls
                            style="width:100%;height:220px;background:#f5f5f5;border-radius:8px;">
                        </model-viewer>"""
                        components.html(html, height=230)
                    else:
                        st.video(src["url"])
                elif f.get("url"):
                    st.write(f"📄 **{f.get('mimeType', 'File')}**")
                    st.write(f"{(f.get('originalFileSize') or 0) / 1024:.1f} KB")
                    st.link_button("Open file ↗", f["url"])
                st.caption(f.get("alt") or "—")
                st.caption(f.get("createdAt", "")[:10])

    page_info = data.get("pageInfo", {})
    if page_info.get("hasNextPage"):
        if st.button("⬇️ Load more files"):
            more = fetch_files_full(first=count, after=page_info.get("endCursor"))
            st.session_state.files_library_data["edges"].extend(more["edges"])
            st.session_state.files_library_data["pageInfo"] = more["pageInfo"]
            st.rerun()
