# ⚡ Quick Start — Real-Time Shopify Sync in 5 Minutes

Get your Shopify store connected with automatic data syncing running in 5 minutes.

## Prerequisites
- Python 3.10+
- A Shopify store with Admin access
- 5 minutes

## Step 1: Install (1 min)

```bash
cd jewellery_erp
pip install -r requirements.txt
```

## Step 2: Run the app (1 min)

```bash
streamlit run app.py
```

Browser opens to `http://localhost:8501` automatically.

## Step 3: Connect Shopify (2 min)

**Go to: Shopify Sync → Connect Store (OAuth)**

Two options:

### Option A: Quick OAuth (Recommended)
1. Create app in [Shopify Partner Dashboard](https://partners.shopify.com)
2. Get **Client ID** and **Client Secret**
3. Paste into ERP form along with your redirect URL
4. Enter your store domain
5. Click **Connect to Store**
6. ✅ Approve on Shopify, you're connected!

### Option B: Manual Token (No public URL needed)
1. In Shopify Admin: **Settings → Develop apps → Create app**
2. Copy the **Admin API access token**
3. Paste into ERP form: **Advanced: connect with manual token**
4. ✅ Save and connected!

## Step 4: First Sync (1 min)

**Go to: Shopify Sync → Sync Products/Orders/Customers**

Click the blue sync button:
- ⬇️ **Sync Products Now** — imports all your Shopify products
- ⬇️ **Sync Orders Now** — imports all your Shopify orders
- ⬇️ **Sync Customers Now** — imports all your customers

Watch the progress, you'll see how many were imported.

## Step 5: Enable Auto-Sync (Optional but Recommended)

**Go to: Shopify Sync → Auto-Sync Settings**

1. ✅ Check **Enable automatic syncing**
2. Set interval to **15 minutes** (default, adjust as needed)
3. Select what to sync: Products ✅, Orders ✅, Customers ✅
4. Click **Save Auto-Sync Config**

**That's it!** Data will now sync automatically every 15 minutes.

---

## For Production (Background Worker)

To keep syncing 24/7 even when Streamlit app restarts:

### Simple way (Linux):
```bash
python background_sync_worker.py &
```

### Better way (Systemd service):
```bash
# Create service file
sudo nano /etc/systemd/system/jewellery-erp-sync.service
```

Paste this:
```ini
[Unit]
Description=Jewellery ERP Shopify Sync
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/jewellery_erp
ExecStart=/usr/bin/python3 background_sync_worker.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable jewellery-erp-sync
sudo systemctl start jewellery-erp-sync
sudo systemctl status jewellery-erp-sync
```

### Docker:
```bash
docker build -t jewellery-erp .
docker run -d jewellery-erp python background_sync_worker.py
```

---

## ✅ You're Done!

Your Shopify store is now syncing automatically. Your ERP will:

✨ **Every 15 minutes:**
- Pull new products from Shopify
- Pull new orders from Shopify
- Pull new customers from Shopify
- Detect and prevent duplicates
- Log everything for audit trail

✨ **Manual sync anytime:**
- Go to Shopify Sync and click sync buttons
- Check Sync History for status

✨ **Dashboard shows:**
- Product count, latest orders, low stock alerts
- All synced from Shopify in real-time

---

## Troubleshooting

**"Connection failed"**
- Check Client ID, Secret, and Redirect URI are correct
- Try the manual token method instead

**"Auto-sync disabled" message**
- Background worker isn't running
- Start it: `python background_sync_worker.py`

**Products not syncing**
- Check Shopify Sync page for connection status
- Look at Sync History for errors
- Check `sync_worker.log` for details

**Need more help?**
- See `REALTIME_SYNC_SETUP.md` for detailed setup
- Check `README.md` for features overview

---

## What's Next?

1. **Explore the app**: Click through Products, Orders, Customers pages
2. **Set up invoicing**: Go to Invoicing page to generate PDFs
3. **Configure pricing**: Pricing Calculator to set metal rates
4. **View reports**: Check Reports page for insights

---

**Sync Status**: 
- Check **Shopify Sync → Sync History** anytime to see latest sync status
- Check `sync_worker.log` for detailed debug info

**Questions?** See full docs in `REALTIME_SYNC_SETUP.md`

🎉 **Enjoy your synced ERP!**
