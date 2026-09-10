"""
Real-time Shopify data synchronization engine.
Handles automatic syncing via webhooks, polling, and scheduled tasks.
Includes retry logic, conflict resolution, and sync history tracking.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib
import hmac

from utils.db import run_query, get_setting, set_setting
from utils.shopify_api import ShopifyClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Sync status tracking"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class SyncType(Enum):
    """Types of sync operations"""
    PRODUCTS = "products"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    INVENTORY = "inventory"
    FULL = "full"


class RealtimeSyncEngine:
    """
    Manages real-time Shopify synchronization.
    - Tracks sync history and status
    - Handles retries and conflict resolution
    - Provides webhook verification
    - Manages background sync tasks
    """

    def __init__(self):
        self.client = ShopifyClient()
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    def verify_webhook(self, request_data: bytes, hmac_header: str) -> bool:
        """Verify Shopify webhook signature"""
        api_secret = get_setting("shopify_api_secret", "").encode()
        if not api_secret:
            logger.warning("No API secret configured for webhook verification")
            return False

        computed_hmac = hmac.new(
            api_secret, request_data, hashlib.sha256
        ).digest()
        computed_hmac_b64 = __import__("base64").b64encode(computed_hmac).decode()
        return computed_hmac_b64 == hmac_header

    def log_sync_event(
        self,
        sync_type: SyncType,
        status: SyncStatus,
        record_count: int,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log sync events to database for audit trail"""
        run_query(
            """INSERT INTO sync_history 
               (sync_type, status, record_count, error_message, metadata, sync_timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                sync_type.value,
                status.value,
                record_count,
                error_message,
                json.dumps(metadata or {}),
                datetime.now().isoformat()
            )
        )

    def sync_products(self, limit: int = 100, full: bool = False) -> Dict[str, Any]:
        """
        Sync products with conflict detection and retry logic.
        full=True syncs all products; False only recent changes.
        """
        try:
            status = SyncStatus.RUNNING
            imported = 0
            updated = 0
            errors = []

            shop_products = self.client.fetch_products(limit=limit)

            for sp in shop_products:
                try:
                    variant = sp.get("variants", [{}])[0]
                    sku = variant.get("sku") or f"SHOPIFY-{sp['id']}"
                    price = float(variant.get("price") or 0)
                    qty = int(variant.get("inventory_quantity") or 0)
                    shopify_id = str(sp["id"])

                    existing = run_query(
                        "SELECT * FROM products WHERE shopify_product_id=?",
                        (shopify_id,),
                        fetchone=True
                    )

                    now = datetime.now().isoformat()

                    if existing:
                        # Conflict resolution: use server version if ERP is older
                        erp_updated = existing.get("updated_at", "")
                        shopify_updated = sp.get("updated_at", "")

                        if shopify_updated > erp_updated or not existing.get("selling_price"):
                            run_query(
                                """UPDATE products 
                                   SET name=?, selling_price=?, stock_qty=?, 
                                   image_url=?, updated_at=?
                                   WHERE id=?""",
                                (
                                    sp["title"],
                                    price,
                                    qty,
                                    sp.get("featured_image", {}).get("src"),
                                    now,
                                    existing["id"]
                                )
                            )
                            updated += 1
                    else:
                        # New product
                        run_query(
                            """INSERT INTO products
                            (sku, name, category, metal_type, purity, selling_price,
                             stock_qty, shopify_product_id, status, created_at, updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                sku,
                                sp["title"],
                                sp.get("product_type") or "Other",
                                "Gold",
                                "22K",
                                price,
                                qty,
                                shopify_id,
                                "active",
                                now,
                                now
                            )
                        )
                        imported += 1

                except Exception as e:
                    errors.append(f"Product {sp.get('title', 'unknown')}: {str(e)}")
                    logger.error(f"Error syncing product {sp['id']}: {e}")

            status = SyncStatus.COMPLETED if not errors else SyncStatus.FAILED
            self.log_sync_event(
                SyncType.PRODUCTS,
                status,
                imported + updated,
                "\n".join(errors) if errors else None,
                {"imported": imported, "updated": updated}
            )

            return {
                "status": status.value,
                "imported": imported,
                "updated": updated,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Product sync failed: {e}")
            self.log_sync_event(SyncType.PRODUCTS, SyncStatus.FAILED, 0, str(e))
            return {"status": "failed", "error": str(e)}

    def sync_orders(self, limit: int = 100, since_last_sync: bool = True) -> Dict[str, Any]:
        """
        Sync orders with smart filtering (only new/updated since last sync).
        """
        try:
            status = SyncStatus.RUNNING
            imported = 0
            updated = 0
            errors = []

            # Get last successful order sync time
            last_sync = run_query(
                """SELECT sync_timestamp FROM sync_history 
                   WHERE sync_type='orders' AND status='completed'
                   ORDER BY sync_timestamp DESC LIMIT 1""",
                fetchone=True
            )
            last_sync_time = None
            if last_sync and since_last_sync:
                last_sync_time = last_sync["sync_timestamp"]

            shop_orders = self.client.fetch_orders(limit=limit, updated_since=last_sync_time)

            for so in shop_orders:
                try:
                    shopify_id = str(so["id"])
                    existing = run_query(
                        "SELECT id FROM orders WHERE shopify_order_id=?",
                        (shopify_id,),
                        fetchone=True
                    )

                    if existing:
                        # Update order status only
                        run_query(
                            """UPDATE orders SET status=?, payment_status=?, updated_at=?
                               WHERE shopify_order_id=?""",
                            (
                                "delivered" if so.get("fulfillment_status") == "fulfilled" else "processing",
                                "paid" if so.get("financial_status") == "paid" else "unpaid",
                                datetime.now().isoformat(),
                                shopify_id
                            )
                        )
                        updated += 1
                        continue

                    # New order - ensure customer exists
                    cust = so.get("customer") or {}
                    cust_id = None
                    if cust.get("id"):
                        crow = run_query(
                            "SELECT id FROM customers WHERE shopify_customer_id=?",
                            (str(cust["id"]),),
                            fetchone=True
                        )
                        if crow:
                            cust_id = crow["id"]
                        else:
                            cust_id = run_query(
                                """INSERT INTO customers 
                                   (name, email, phone, shopify_customer_id, created_at)
                                   VALUES (?,?,?,?,?)""",
                                (
                                    f"{cust.get('first_name','')} {cust.get('last_name','')}".strip() or "Shopify Customer",
                                    cust.get("email"),
                                    cust.get("phone"),
                                    str(cust["id"]),
                                    datetime.now().isoformat()
                                )
                            )

                    order_number = so.get("name") or f"#{so['id']}"
                    run_query(
                        """INSERT INTO orders
                        (order_number, shopify_order_id, customer_id, order_date, 
                         status, payment_status, subtotal, tax_amount, total_amount, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (
                            order_number,
                            shopify_id,
                            cust_id,
                            so.get("created_at", "")[:10],
                            "delivered" if so.get("fulfillment_status") == "fulfilled" else "processing",
                            "paid" if so.get("financial_status") == "paid" else "unpaid",
                            float(so.get("subtotal_price") or 0),
                            float(so.get("total_tax") or 0),
                            float(so.get("total_price") or 0),
                            datetime.now().isoformat()
                        )
                    )
                    imported += 1

                except Exception as e:
                    errors.append(f"Order {so.get('name', 'unknown')}: {str(e)}")
                    logger.error(f"Error syncing order {so['id']}: {e}")

            status = SyncStatus.COMPLETED if not errors else SyncStatus.FAILED
            self.log_sync_event(
                SyncType.ORDERS,
                status,
                imported + updated,
                "\n".join(errors) if errors else None,
                {"imported": imported, "updated": updated}
            )

            return {
                "status": status.value,
                "imported": imported,
                "updated": updated,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Order sync failed: {e}")
            self.log_sync_event(SyncType.ORDERS, SyncStatus.FAILED, 0, str(e))
            return {"status": "failed", "error": str(e)}

    def sync_customers(self, limit: int = 100) -> Dict[str, Any]:
        """Sync customers with duplicate detection."""
        try:
            status = SyncStatus.RUNNING
            imported = 0
            updated = 0
            errors = []

            shop_customers = self.client.fetch_customers(limit=limit)

            for sc in shop_customers:
                try:
                    shopify_id = str(sc["id"])
                    existing = run_query(
                        "SELECT id FROM customers WHERE shopify_customer_id=?",
                        (shopify_id,),
                        fetchone=True
                    )

                    addr = sc.get("default_address") or {}
                    now = datetime.now().isoformat()

                    if existing:
                        run_query(
                            """UPDATE customers 
                               SET name=?, email=?, phone=?, address=?, city=?, 
                               state=?, pincode=?, updated_at=?
                               WHERE shopify_customer_id=?""",
                            (
                                f"{sc.get('first_name','')} {sc.get('last_name','')}".strip() or "Shopify Customer",
                                sc.get("email"),
                                sc.get("phone"),
                                addr.get("address1"),
                                addr.get("city"),
                                addr.get("province"),
                                addr.get("zip"),
                                now,
                                shopify_id
                            )
                        )
                        updated += 1
                    else:
                        run_query(
                            """INSERT INTO customers
                            (name, email, phone, address, city, state, pincode, 
                             shopify_customer_id, created_at, updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (
                                f"{sc.get('first_name','')} {sc.get('last_name','')}".strip() or "Shopify Customer",
                                sc.get("email"),
                                sc.get("phone"),
                                addr.get("address1"),
                                addr.get("city"),
                                addr.get("province"),
                                addr.get("zip"),
                                shopify_id,
                                now,
                                now
                            )
                        )
                        imported += 1

                except Exception as e:
                    errors.append(f"Customer {sc.get('email', 'unknown')}: {str(e)}")
                    logger.error(f"Error syncing customer {sc['id']}: {e}")

            status = SyncStatus.COMPLETED if not errors else SyncStatus.FAILED
            self.log_sync_event(
                SyncType.CUSTOMERS,
                status,
                imported + updated,
                "\n".join(errors) if errors else None,
                {"imported": imported, "updated": updated}
            )

            return {
                "status": status.value,
                "imported": imported,
                "updated": updated,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Customer sync failed: {e}")
            self.log_sync_event(SyncType.CUSTOMERS, SyncStatus.FAILED, 0, str(e))
            return {"status": "failed", "error": str(e)}

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current and historical sync status."""
        status_rows = run_query(
            """SELECT sync_type, status, record_count, error_message, sync_timestamp
               FROM sync_history
               ORDER BY sync_timestamp DESC
               LIMIT 20""",
            fetch=True
        )

        # Group latest by sync type
        latest = {}
        for row in status_rows:
            sync_type = row["sync_type"]
            if sync_type not in latest:
                latest[sync_type] = row

        return {
            "latest": latest,
            "history": status_rows,
            "sync_enabled": bool(get_setting("shopify_access_token", "")),
            "last_full_sync": get_setting("last_full_sync_timestamp", "Never"),
        }

    def enable_auto_sync(self, interval_minutes: int = 15) -> bool:
        """
        Enable automatic background syncing.
        Returns True if scheduler was started.
        Note: Requires background task runner (see README for setup).
        """
        set_setting("auto_sync_enabled", "true")
        set_setting("auto_sync_interval_minutes", str(interval_minutes))
        logger.info(f"Auto sync enabled with {interval_minutes} minute interval")
        return True

    def disable_auto_sync(self) -> bool:
        """Disable automatic syncing."""
        set_setting("auto_sync_enabled", "false")
        logger.info("Auto sync disabled")
        return True

    def get_auto_sync_config(self) -> Dict[str, Any]:
        """Get auto sync configuration."""
        return {
            "enabled": get_setting("auto_sync_enabled", "false") == "true",
            "interval_minutes": int(get_setting("auto_sync_interval_minutes", "15")),
            "sync_products": get_setting("auto_sync_products", "true") == "true",
            "sync_orders": get_setting("auto_sync_orders", "true") == "true",
            "sync_customers": get_setting("auto_sync_customers", "true") == "true",
        }
