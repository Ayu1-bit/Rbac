"""
Database layer for Jewellery ERP
Uses SQLite for zero-config local persistence.
"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jewellery_erp.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            metal_type TEXT,
            purity TEXT,
            gross_weight REAL DEFAULT 0,
            net_weight REAL DEFAULT 0,
            stone_weight REAL DEFAULT 0,
            stone_type TEXT,
            stone_cost REAL DEFAULT 0,
            making_charge_type TEXT DEFAULT 'per_gram',
            making_charge_value REAL DEFAULT 0,
            cost_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            stock_qty INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 2,
            hsn_code TEXT DEFAULT '7113',
            barcode TEXT,
            shopify_product_id TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            loyalty_points REAL DEFAULT 0,
            shopify_customer_id TEXT,
            created_at TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            shopify_order_id TEXT,
            customer_id INTEGER,
            order_date TEXT,
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'unpaid',
            subtotal REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            shipping_address TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            price REAL DEFAULT 0,
            metal_rate_at_sale REAL DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            material_type TEXT,
            gst_number TEXT,
            created_at TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            supplier_id INTEGER,
            po_date TEXT,
            status TEXT DEFAULT 'draft',
            total_amount REAL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER,
            material_type TEXT,
            purity TEXT,
            weight REAL DEFAULT 0,
            rate_per_gram REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS manufacturing_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            karigar_name TEXT,
            description TEXT,
            product_id INTEGER,
            given_weight REAL DEFAULT 0,
            received_weight REAL DEFAULT 0,
            wastage REAL DEFAULT 0,
            labour_charge REAL DEFAULT 0,
            status TEXT DEFAULT 'assigned',
            start_date TEXT,
            expected_date TEXT,
            completed_date TEXT,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            order_id INTEGER,
            invoice_date TEXT,
            subtotal REAL DEFAULT 0,
            gst_amount REAL DEFAULT 0,
            total REAL DEFAULT 0,
            pdf_path TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS metal_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metal_type TEXT,
            purity TEXT,
            rate_per_gram REAL,
            rate_date TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT NOT NULL,
            status TEXT NOT NULL,
            record_count INTEGER DEFAULT 0,
            error_message TEXT,
            metadata TEXT,
            sync_timestamp TEXT NOT NULL
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )""")

        # Add updated_at column if it doesn't exist (for orders and customers)
        try:
            c.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT")
        except:
            pass

        try:
            c.execute("ALTER TABLE customers ADD COLUMN updated_at TEXT")
        except:
            pass

        # POS / role-tracking columns on orders
        try:
            c.execute("ALTER TABLE orders ADD COLUMN created_by_user_id INTEGER")
        except:
            pass

        try:
            c.execute("ALTER TABLE orders ADD COLUMN channel TEXT DEFAULT 'manual'")
        except:
            pass

        # Seed a default admin user if no users exist yet
        c.execute("SELECT COUNT(*) as cnt FROM users")
        if c.fetchone()["cnt"] == 0:
            import bcrypt
            default_password = "admin123"
            pw_hash = bcrypt.hashpw(default_password.encode(), bcrypt.gensalt()).decode()
            c.execute(
                "INSERT INTO users (username, password_hash, full_name, role, active) VALUES (?,?,?,?,1)",
                ("admin", pw_hash, "Administrator", "admin"),
            )
            print(f"[Jewellery ERP] Created default admin user — username: admin  password: {default_password}")
            print("[Jewellery ERP] Please log in and change this password immediately (Settings → Users).")

        # seed default settings
        defaults = {
            "company_name": "Aurum Jewels",
            "gst_number": "",
            "address": "",
            "phone": "",
            "email": "",
            "currency_symbol": "₹",
            "gst_rate": "3",
            "shopify_store_url": "",
            "shopify_access_token": "",
            "shopify_api_version": "2026-07",
            "shopify_client_id": "",
            "shopify_client_secret": "",
            "shopify_redirect_uri": "",
            "shopify_scopes": (
                "read_products,write_products,read_orders,write_orders,read_all_orders,"
                "read_draft_orders,write_draft_orders,read_customers,write_customers,"
                "read_inventory,write_inventory,read_locations,read_fulfillments,write_fulfillments,"
                "read_files,write_files,read_price_rules,read_discounts,read_content,read_shipping"
            ),
            "shopify_oauth_state": "",
            "shopify_granted_scopes": "",
            "shopify_refresh_token": "",
            "shopify_token_expires_at": "",
            "shopify_refresh_expires_at": "",
            "shopify_shop_name": "",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Shopify role permissions
        c.execute("""CREATE TABLE IF NOT EXISTS shopify_role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            resource TEXT NOT NULL,
            can_view INTEGER DEFAULT 0,
            can_create INTEGER DEFAULT 0,
            can_edit INTEGER DEFAULT 0,
            can_delete INTEGER DEFAULT 0,
            can_sync INTEGER DEFAULT 0,
            UNIQUE(role, resource)
        )""")
        # seed permissions for current built-in roles
        try:
            from utils.shopify_permissions import SHOPIFY_RESOURCES
            roles = ["admin", "manager", "sales", "production", "accountant", "purchasing"]
            for role in roles:
                for resource, _ in SHOPIFY_RESOURCES:
                    v = 1 if role == "admin" else 0
                    c.execute("""INSERT OR IGNORE INTO shopify_role_permissions
                        (role, resource, can_view, can_create, can_edit, can_delete, can_sync)
                        VALUES (?,?,?,?,?,?,?)""", (role, resource, v, v, v, v, v))
        except Exception:
            pass

        # seed a default gold/silver rate if none exists
        c.execute("SELECT COUNT(*) as cnt FROM metal_rates")
        if c.fetchone()["cnt"] == 0:
            today = datetime.now().strftime("%Y-%m-%d")
            c.executemany(
                "INSERT INTO metal_rates (metal_type, purity, rate_per_gram, rate_date) VALUES (?,?,?,?)",
                [
                    ("Gold", "24K", 7200.0, today),
                    ("Gold", "22K", 6600.0, today),
                    ("Gold", "18K", 5400.0, today),
                    ("Silver", "999", 92.0, today),
                    ("Platinum", "950", 3200.0, today),
                ],
            )


def run_query(query, params=(), fetch=False, fetchone=False):
    with get_conn() as conn:
        cur = conn.execute(query, params)
        if fetchone:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch:
            return [dict(r) for r in cur.fetchall()]
        return cur.lastrowid


def get_setting(key, default=""):
    row = run_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return row["value"] if row else default


def set_setting(key, value):
    run_query("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def next_number(prefix, table, number_col):
    """Generate a sequential document number like PO-0001, INV-0001 etc."""
    row = run_query(f"SELECT COUNT(*) as cnt FROM {table}", fetchone=True)
    n = (row["cnt"] or 0) + 1
    return f"{prefix}-{n:04d}"
