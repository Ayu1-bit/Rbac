
import json
import streamlit as st
from utils.db import init_db
from utils.auth import require_role, current_user, render_sidebar_user_box
from utils.shopify_graphql_client import ShopifyGraphQLClient
from utils.shopify_permissions import can, scope_available

st.set_page_config(page_title="Shopify Control Center · Jewellery ERP", page_icon="🛍️", layout="wide")
init_db()
require_role()
render_sidebar_user_box()

user = current_user()
role = user["role"]

RESOURCE_QUERIES = {
"overview": """query { shop { id name email currencyCode primaryDomain { host } plan { displayName } } }""",
"products": """query { products(first: 50) { nodes { id title handle status vendor productType tags descriptionHtml createdAt updatedAt totalInventory featuredImage { url altText } variants(first: 50) { nodes { id title sku price compareAtPrice inventoryQuantity selectedOptions { name value } } } } } }""",
"orders": """query { orders(first: 50, sortKey: CREATED_AT, reverse: true) { nodes { id name createdAt updatedAt displayFinancialStatus displayFulfillmentStatus email phone totalPriceSet { shopMoney { amount currencyCode } } customer { id displayName email } lineItems(first: 50) { nodes { title quantity sku originalUnitPriceSet { shopMoney { amount currencyCode } } } } } } }""",
"customers": """query { customers(first: 50) { nodes { id displayName firstName lastName email phone state createdAt updatedAt numberOfOrders amountSpent { amount currencyCode } defaultEmailAddress { email } defaultPhoneNumber { phoneNumber } defaultAddress { address1 address2 city province country zip } } } }""",
"collections": """query { collections(first: 50) { nodes { id title handle descriptionHtml updatedAt productsCount { count } } } }""",
"inventory": """query { locations(first: 50) { nodes { id name isActive address { address1 city province country zip } } } }""",
"locations": """query { locations(first: 50) { nodes { id name isActive fulfillsOnlineOrders address { address1 city province country zip } } } }""",
"discounts": """query { discountNodes(first: 50) { nodes { id discount { __typename ... on DiscountCodeBasic { title status startsAt endsAt } ... on DiscountAutomaticBasic { title status startsAt endsAt } } } } }""",
"draft_orders": """query { draftOrders(first: 50) { nodes { id name status createdAt updatedAt totalPriceSet { shopMoney { amount currencyCode } } } } }""",
"fulfillments": """query { orders(first: 25) { nodes { id name fulfillments(first: 20) { id status createdAt trackingInfo { number url company } } } } }""",
"returns": """query { orders(first: 25, query:"status:any") { nodes { id name returnStatus returns(first: 20) { nodes { id status name createdAt } } } } }""",
"files": """query { files(first: 50) { nodes { id fileStatus alt createdAt ... on MediaImage { image { url altText } } } } }""",
"content": """query { pages(first: 50) { nodes { id title handle bodySummary isPublished createdAt updatedAt } } }""",
"navigation": """query { menus(first: 50) { nodes { id title handle items { id title url type } } } }""",
"markets": """query { markets(first: 50) { nodes { id name handle status } } }""",
"metafields": """query { shop { metafields(first: 50) { nodes { id namespace key value type ownerType } } } }""",
"locales": """query { shopLocales { locale name primary published } }""",
"reports": """query { shop { id name } }""",
}

labels = {
"overview":"Store / Overview","products":"Products","orders":"Orders","customers":"Customers",
"collections":"Collections","inventory":"Inventory","locations":"Locations","discounts":"Discounts",
"draft_orders":"Draft Orders","fulfillments":"Fulfillments","returns":"Returns","files":"Files / Media",
"content":"Online Store Content","navigation":"Navigation","markets":"Markets","metafields":"Metafields",
"locales":"Locales / Translations","reports":"Reports / Analytics"
}

st.title("🛍️ Shopify Control Center")
st.caption("Universal Shopify data view. The ERP uses Shopify's Admin GraphQL API for the live store data.")
client = ShopifyGraphQLClient()
if not client.configured:
    st.error("Shopify is not connected. An administrator must connect the store once.")
    st.stop()

resources = [r for r in RESOURCE_QUERIES if can(role, r, "view")]
if not resources:
    st.warning("Your role has no Shopify resources assigned.")
    st.stop()

resource = st.selectbox("Shopify data", resources, format_func=lambda x: labels.get(x,x))
c1,c2=st.columns([1,1])
with c1:
    if st.button("🔄 Load live Shopify data", type="primary", disabled=not can(role, resource, "view")):
        try:
            data=client.execute(RESOURCE_QUERIES[resource])
            st.session_state["shopify_live_data"]=data
            st.session_state["shopify_resource"]=resource
        except Exception as e:
            st.error(str(e))
with c2:
    st.metric("Write access", "YES" if can(role, resource, "edit") else "NO")

if "shopify_live_data" in st.session_state and st.session_state.get("shopify_resource")==resource:
    data=st.session_state["shopify_live_data"]
    st.subheader(f"Live {labels.get(resource,resource)}")
    st.json(data, expanded=False)

st.divider()
st.subheader("⚙️ Advanced Shopify API editor")
st.caption("This is intentionally resource-gated. The selected role must have Edit/Create/Delete permission, and Shopify must have granted the required write scope. This lets the ERP expose Shopify fields that are added by Shopify without requiring a new ERP release.")

default_mutation = """mutation { }"""
mutation = st.text_area("GraphQL mutation", value=default_mutation, height=180,
                         disabled=not can(role, resource, "edit"),
                         help="Paste a Shopify Admin GraphQL mutation for the selected resource.")
variables_text = st.text_area("Variables JSON (optional)", value="{}", height=100,
                               disabled=not can(role, resource, "edit"))
if st.button("🚀 Run Shopify change", type="primary",
             disabled=not can(role, resource, "edit") or not scope_available(resource, "edit")):
    try:
        variables=json.loads(variables_text or "{}")
        result=client.execute(mutation, variables)
        st.success("Shopify change completed.")
        st.json(result)
    except Exception as e:
        st.error(str(e))

st.caption("The Shopify Admin API remains the source of truth. The ERP never exposes the Admin API token to the browser.")
