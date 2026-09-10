# Real-Time Shopify Sync Setup Guide

This ERP now includes automatic real-time synchronization with Shopify. This document covers setup, configuration, and troubleshooting.

## Quick Start

### 1. First-Time Connection

1. **Go to Settings → Shopify Sync**
2. **OAuth Flow (Recommended):**
   - Create a Shopify app in the [Partner Dashboard](https://partners.shopify.com)
   - Set App URL and Redirect URI to your app's public URL (e.g., `https://your-erp.streamlit.app`)
   - Copy Client ID and Client Secret
   - Paste into the "Connect Store" section
   - Click "🚀 Connect to Store" and approve the install
   - Your access token is automatically saved

3. **First Sync:**
   - Go to **Shopify Sync → Sync Products** and click "⬇️ Sync Products Now"
   - Repeat for Orders and Customers
   - Check **Sync History** tab to verify

### 2. Enable Automatic Sync

In **Shopify Sync → Auto-Sync Settings (Real-Time):**

- ✅ Check "Enable automatic syncing"
- Set interval to **15 minutes** (or your preferred frequency)
- Select which data types to sync (Products, Orders, Customers)
- Click "💾 Save Auto-Sync Config"

### 3. Deploy Background Worker (Production Only)

For automatic syncing to work 24/7, you need a background process:

**Option A: Local/Development (one-time test)**
```bash
pip install -r requirements.txt
python background_sync_worker.py
```

**Option B: Systemd (Linux production)**

Create `/etc/systemd/system/jewellery-erp-sync.service`:

```ini
[Unit]
Description=Jewellery ERP Shopify Sync Worker
After=network.target

[Service]
Type=simple
User=erp_user
WorkingDirectory=/opt/jewellery_erp
ExecStart=/opt/jewellery_erp/venv/bin/python background_sync_worker.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/jewellery_erp_sync.log
StandardError=append:/var/log/jewellery_erp_sync.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable jewellery-erp-sync
sudo systemctl start jewellery-erp-sync
sudo systemctl status jewellery-erp-sync
```

Check logs:
```bash
sudo tail -f /var/log/jewellery_erp_sync.log
```

**Option C: Docker (containerized deployment)**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "background_sync_worker.py"]
```

**Option D: Streamlit Cloud or Heroku**

Both platforms require adding a background worker:

Streamlit Cloud `.streamlit/config.toml`:
```toml
[runner]
magicEnabled = true
runOnSave = true
```

Create `Procfile` for Heroku:
```
web: streamlit run app.py
worker: python background_sync_worker.py
```

## How It Works

### Data Flow

```
Shopify Store
    ↓
Scheduled Worker (every 15 min)
    ↓
Real-Time Sync Engine
    ├─ Fetch products with conflict detection
    ├─ Sync orders (incremental since last sync)
    └─ Sync customers with duplicate detection
    ↓
Local SQLite Database
    ↓
Streamlit Dashboard (live updates)
```

### Smart Syncing Features

1. **Incremental Updates**: Only fetches data modified since last sync
2. **Conflict Resolution**: ERP data takes precedence if manually modified
3. **Duplicate Detection**: Prevents creating duplicate customer records
4. **Rate Limiting**: Respects Shopify API rate limits automatically
5. **Retry Logic**: Automatically retries failed requests with exponential backoff
6. **Sync History**: Full audit trail of all sync operations

### Manual Sync Anytime

Even with auto-sync enabled, you can manually sync:
- **Shopify Sync → Sync Products/Orders/Customers tabs**: One-click sync
- **Sync History tab**: View all past syncs and status

## Configuration Options

### Auto-Sync Settings (in Settings page)

| Setting | Default | Range | Purpose |
|---------|---------|-------|---------|
| Sync Interval | 15 min | 5-120 min | How often to check Shopify |
| Sync Products | On | - | Auto-sync products |
| Sync Orders | On | - | Auto-sync orders |
| Sync Customers | On | - | Auto-sync customers |

### Advanced (in database)

| Key | Default | Notes |
|-----|---------|-------|
| `auto_sync_enabled` | false | Set to "true" to enable |
| `auto_sync_interval_minutes` | 15 | Minimum 5, max 120 |
| `shopify_api_version` | 2024-10 | Update as needed |

## Monitoring & Troubleshooting

### Check Sync Status

1. **Dashboard**: KPI cards show recent sync status
2. **Shopify Sync → Sync History**: Full audit trail with timestamps
3. **Logs**: 
   - Local: `sync_worker.log`
   - Systemd: `sudo journalctl -u jewellery-erp-sync -f`

### Common Issues

**❌ "Auto-sync disabled" message**
- Worker process is not running
- Start with: `python background_sync_worker.py`

**❌ Sync is taking too long**
- Shopify API rate limit reached → Worker backs off automatically
- Check `sync_worker.log` for rate limit warnings
- Increase interval time in settings if frequent

**❌ Products/orders not updating**
- Check Shopify Sync page for connection status
- Verify access token is still valid (re-connect if needed)
- Check **Sync History** tab for error messages
- Look at `sync_worker.log` for detailed errors

**❌ "Connection failed" during initial setup**
- Verify Shopify app credentials are correct
- Check redirect URI matches exactly (case-sensitive)
- Ensure your app has proper scopes: `read_products,read_orders,read_customers,write_inventory`

**❌ Database locked errors**
- Multiple sync processes running simultaneously
- Kill existing: `pkill -f background_sync_worker`
- Check only one worker is running: `ps aux | grep background_sync_worker`

### Performance Optimization

For stores with 10K+ products/orders:

1. **Increase sync interval** to 30-60 minutes (less frequent)
2. **Limit batch size** in sync page (don't fetch all 250 at once)
3. **Enable incremental sync** (default) to fetch only recent changes
4. **Use separate database** (migrate from SQLite to PostgreSQL for production)

## Webhook Integration (Advanced)

For true real-time updates (vs polling), you can set up Shopify webhooks:

1. **Shopify Partner Dashboard → App setup → Webhooks**
2. **Subscribe to topics**: 
   - `products/update`, `products/create`
   - `orders/create`, `orders/update`
   - `customers/create`, `customers/update`
3. **Webhook URL**: `https://your-app.com/api/webhook` (requires custom backend)

*Currently not implemented, but planned for v2.*

## Data Reconciliation

If data gets out of sync:

1. **Manual re-sync**: Go to Shopify Sync → Re-sync all data
2. **Reset sync history**: 
   ```sql
   DELETE FROM sync_history;
   ```
3. **Force full sync**:
   ```bash
   # In Python shell or worker log
   from utils.shopify_realtime_sync import RealtimeSyncEngine
   engine = RealtimeSyncEngine()
   engine.sync_products(limit=250, full=True)  # Full resync
   ```

## API Scopes Required

Ensure your Shopify app has these scopes:

```
read_products,write_products
read_orders,write_orders,read_all_orders
read_customers,write_customers
read_inventory,write_inventory
read_locations
read_fulfillments,write_fulfillments
read_price_rules
read_files,write_files
```

If missing, disconnect and reconnect through OAuth to grant new permissions.

## Security

- **Access tokens** are stored encrypted in local database
- **Webhooks**: Always verify HMAC signature (implemented)
- **Rate limiting**: Automatic, respects Shopify's rate limits
- **No sensitive data**: Only transactional data (products, orders) is synced

## Support & Debugging

Enable debug mode to see detailed logs:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Then check `sync_worker.log` for detailed request/response information.

---

**Version**: 2.0 (Real-Time Sync)  
**Last Updated**: September 2026  
**Next Steps**: 
- [ ] Webhook integration for true real-time
- [ ] Multi-location inventory sync
- [ ] GraphQL endpoint support
