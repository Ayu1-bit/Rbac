# 💎 Jewellery ERP — for Shopify Stores

A complete, self-hosted ERP system built with **Streamlit** for managing a jewellery business that
sells through Shopify. Runs locally (or on any server) and stores data in a local SQLite database
(`data/jewellery_erp.db`) — no external database required.

## Features

| Module | What it does |
|---|---|
| **Dashboard** | KPIs, sales trend, stock-by-category chart, low-stock alerts, live metal rates, recent orders |
| **Products** | Full jewellery attributes: metal type, purity, gross/net weight, stone weight & cost, making charges (per gram / % / fixed), auto price calculation, stock, reorder level, Shopify product ID link |
| **Orders** | Manual order entry with cart-style line items, status & payment tracking, auto stock deduction |
| **Customers** | CRM with purchase history, loyalty points, 360° customer view |
| **Suppliers & Purchases** | Supplier directory + purchase orders for raw gold/silver/platinum/gemstones |
| **Manufacturing** | Karigar (artisan) job tracking: metal given vs received, wastage %, labour charges |
| **Invoicing** | Generates a downloadable GST tax-invoice PDF per order |
| **Pricing Calculator** | Manage daily gold/silver/platinum rates; instant price calculator; one-click bulk repricing of all products when rates change |
| **Reports** | Sales trends, inventory valuation, profit margin by product, karigar performance |
| **Shopify Sync** | ✨ **NEW: Real-time automatic syncing** — connect once, data updates automatically every 15 min. OAuth "Install App" flow or manual token. Manual sync anytime. Sync history & audit trail. Smart conflict detection. |
| **Product Explorer** | Live view of every Shopify product: full image gallery, variants table, tags/vendor/type, description, and an inline **3D model viewer** (glTF/GLB) for any product media |
| **Order Explorer** | Live, full-depth order view: customer, shipping/billing address, line items with images, fulfillment/tracking, tags, notes, and a full money breakdown |
| **Files Library** | Every file in your store's Content → Files library — images, videos, 3D models, and generic uploads (PDFs, certificates, etc.) |
| **Settings** | Company info, GST rate, currency symbol, full data reset |

## Setup

1. **Install Python 3.10+** if you don't already have it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```
4. Your browser will open automatically at `http://localhost:8501`.

The SQLite database is created automatically on first run at `data/jewellery_erp.db`, along with
sensible default gold/silver/platinum rates and GST settings. Edit them any time on the
**Settings** and **Pricing Calculator** pages.

## Connecting to Shopify

### Option A — OAuth "Install App" flow (recommended: only Client ID + Client Secret needed)

This is the flow you get when you click "Install" on any real Shopify app — the ERP builds the
install link, you approve it on Shopify's own screen, and the Admin API access token comes back
automatically. No manual token copying.

**⚠️ Requirement: your app must be reachable at a public HTTPS URL.** Shopify's servers redirect
the merchant's browser back to that URL after they approve the install — `localhost` does not
work for this step. Two ways to satisfy this:

- **Deploy publicly** (e.g. Streamlit Community Cloud, a VPS, Render, etc.) and use that URL, or
- **Tunnel your local app** while testing, e.g.:
  ```bash
  streamlit run app.py            # starts on localhost:8501
  ngrok http 8501                 # gives you a public https://xxxx.ngrok-free.app URL
  ```

**Setup steps:**
1. In the [Shopify Partner Dashboard](https://partners.shopify.com), create an app (or use an
   existing one).
2. Under **App setup → URLs**: set **App URL** and **Allowed redirection URL(s)** to your public
   app URL (the ngrok URL or your production domain) — must match exactly, no trailing slash
   mismatches.
3. Copy the app's **Client ID** and **Client secret**.
4. In the ERP, go to **Shopify Sync → Connect Store (OAuth)**, paste the Client ID, Client Secret,
   and the same Redirect URI, then enter your store domain and click **Connect to Store**.
5. Click the generated install link, approve the permissions on Shopify, and you'll land back on
   the dashboard with the access token already saved.

### Option B — Manual custom-app token (works entirely locally, no public URL needed)

1. In Shopify Admin: **Settings → Apps and sales channels → Develop apps → Create an app.**
2. Configure Admin API scopes (same list used by the OAuth flow — products, orders, customers,
   inventory, fulfillments, files, discounts, etc.)
3. Install the app **directly in your own store admin** and copy the generated **Admin API access
   token** — this method doesn't need a redirect URL since you're not going through the public
   OAuth screen.
4. In the ERP, go to **Shopify Sync → Advanced: connect with a manual Admin API token**, paste
   your store domain and the token, save, then **Test Connection**.

### Once connected

**Manual Sync (anytime):**
- Go to **Shopify Sync** and click **Sync Products**, **Sync Orders**, or **Sync Customers**
- Data is imported and matched with existing records (smart conflict detection)
- Full sync history visible in **Sync History** tab for audit trail

**Automatic Real-Time Sync (NEW):**
- Enable in **Shopify Sync → Auto-Sync Settings**
- Choose sync interval (default 15 min), data types to sync
- For continuous background syncing, run background worker (see deployment section)
- Data updates automatically without any manual action
- View sync status and history anytime

**Also available:**
- **Product Explorer** — browse live product data straight from Shopify: full image galleries,
  every variant, and an inline 3D model viewer for jewellery pieces with AR/3D media.
- **Order Explorer** — full order detail live from Shopify: customer, addresses, line-item images,
  fulfillment/tracking, and a complete money breakdown.
- **Files Library** — every image, video, 3D model, and generic file (PDFs, certificates, etc.)
  in your store's Content → Files section.
- **Push to Shopify** — create new products in your ERP and push them to Shopify in one click.

> Your Shopify access token and app secret are stored locally in the SQLite settings table —
> keep your database file private and never commit it to a public repository.

## Pricing formula

```
Metal Value      = Net Weight (g) × Rate per gram
Making Charges   = per-gram rate × weight   OR   % of metal value   OR   fixed amount
Subtotal         = Metal Value + Making Charges + Stone/Diamond Cost
GST              = Subtotal × GST rate %
Final Price      = Subtotal + GST
```

Update metal rates daily on the **Pricing Calculator** page, then use **Bulk Repricing** to
recalculate every product's selling price in one click.

## Project structure

```
jewellery_erp/
├── app.py                          # Dashboard (home page)
├── requirements.txt
├── data/                           # SQLite database (auto-created)
├── invoices/                       # Generated invoice PDFs
├── utils/
│   ├── db.py                       # Schema + query helpers
│   ├── helpers.py                  # Pricing/formatting logic
│   └── shopify_api.py              # Shopify Admin REST API client
└── pages/
    ├── 1_💍_Products.py
    ├── 2_📦_Orders.py
    ├── 3_👥_Customers.py
    ├── 4_🏭_Suppliers_and_Purchases.py
    ├── 5_🛠️_Manufacturing.py
    ├── 6_🧾_Invoicing.py
    ├── 7_💰_Pricing_Calculator.py
    ├── 8_📈_Reports.py
    ├── 9_🔗_Shopify_Sync.py
    └── 10_⚙️_Settings.py
```

## Real-Time Sync Setup

**Connect Shopify once, then data updates automatically.**

### Quick Start
1. Go to **Shopify Sync → Connect Store** and authorize via OAuth
2. Go to **Shopify Sync → Auto-Sync Settings** and enable automatic syncing
3. (Optional) For 24/7 background syncing, run background worker (see Deployment section)

### How It Works
- Automatic polling checks Shopify every 15 minutes (configurable)
- Smart incremental syncing only fetches what changed since last sync
- Conflict detection: ERP data takes priority if manually edited
- Duplicate detection: Prevents duplicate customer records
- Rate limit respecting: Automatically backs off if Shopify rate limit hit
- Full audit trail: Every sync logged with timestamp, status, and error details

**See `REALTIME_SYNC_SETUP.md` for full configuration, deployment, and troubleshooting.**

## Deployment

### Local/Development
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Production with Auto-Sync Background Worker

**Option 1: Systemd (Linux/Ubuntu)**
```bash
# Create service file (see REALTIME_SYNC_SETUP.md for full content)
sudo nano /etc/systemd/system/jewellery-erp-sync.service
sudo systemctl enable jewellery-erp-sync
sudo systemctl start jewellery-erp-sync
```

**Option 2: Docker**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Run Streamlit in one container, worker in another
CMD ["python", "background_sync_worker.py"]
```

**Option 3: Streamlit Community Cloud**
- Deploy main app normally
- For background worker, use a separate service (Render, Railway, etc.) running `background_sync_worker.py`

**Option 4: Heroku**
```
web: streamlit run app.py
worker: python background_sync_worker.py
```

## Architecture Improvements v2.0

✨ **Real-Time Sync Engine**
- Automatic background synchronization
- Smart incremental updates
- Conflict resolution
- Full sync history tracking
- Rate limit handling
- Retry logic with exponential backoff

🔒 **Enhanced Security**
- Better error handling
- Webhook signature verification (ready for webhooks)
- Request/response logging
- Secure token storage

📊 **Better Observability**
- Sync history with full audit trail
- Sync status monitoring
- Error tracking and reporting
- Performance metrics

## Notes & Future

- This is a **single-tenant / single-user** local app by design — for a multi-user deployment,
  put it behind auth (e.g., `streamlit-authenticator`) and host the SQLite file on a persistent
  volume, or swap `utils/db.py` for a Postgres connection.
- **v2.0 now includes real-time auto-sync** — data updates automatically without manual intervention
- **Webhook integration** (true real-time, push-based) planned for v2.1 — would replace polling for instant updates


## Shopify Control Center (RBAC + one-time connection)

The ERP now treats Shopify as the live source of truth while keeping the ERP's own
business tables separate.

### Connection
- The store is connected once through the administrator's Shopify OAuth flow.
- Credentials can be supplied through environment variables (`.env.example`).
- The resulting offline token is persisted server-side; it is never sent to ERP users.
- Expiring offline tokens are refreshed automatically before expiry when Shopify returns
  a refresh token.
- Shopify API version defaults to `2026-07`.

### Role access
`Settings -> Shopify Access` contains an admin-only matrix for every built-in ERP role.
For each Shopify resource the admin can independently grant:
- View
- Create
- Edit
- Delete
- Sync

Shopify OAuth scopes remain the store-level gate; the ERP matrix is the user/role gate.
A role can never grant itself access.

### Live Shopify data
`Shopify Control Center` uses the Shopify Admin GraphQL API to display live Shopify data
for products, variants, orders, customers, collections, inventory, locations, discounts,
draft orders, fulfillments, returns, files, online-store content, navigation, markets,
metafields and locales. The advanced resource editor allows authorized roles to run
Shopify Admin GraphQL mutations for the selected resource, subject to the role matrix
and the store's granted scope.

The ERP's existing local sync remains available for its native Products/Orders/Customers
tables. Live Control Center data does not require copying every Shopify field into the
SQLite schema first.
