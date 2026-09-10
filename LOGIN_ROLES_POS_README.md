# What's new: Login, Roles & POS

## First login
- Username: `admin`
- Password: `admin123`
- **Change this immediately** after first login: Settings → Users & Roles → select `admin` → Reset password.

## Roles
| Role | Sidebar access |
|---|---|
| Administrator | Everything, including Settings and user management |
| Manager | Everything except Settings |
| Sales / POS | Dashboard, POS, Orders, Customers, Order Explorer |
| Production (Karigar) | Dashboard, Manufacturing |
| Accountant | Dashboard, Invoicing, Reports, Pricing Calculator |
| Purchasing | Dashboard, Suppliers & Purchases |

Manage users (create, change role, deactivate, reset password) from **Settings → Users & Roles**
(admin only).

## POS
New **POS** page (top of the sidebar for admin/manager/sales roles): search or scan a product,
build a cart, pick or quick-add a customer, choose a payment method, and complete the sale.
This creates a real order + order items, deducts stock, records which staff member made the
sale, and generates a downloadable PDF receipt immediately using the same invoice template as
the Invoicing page.

## What changed under the hood
- New `users` table + `utils/auth.py` (bcrypt password hashing, session-based login, per-page
  role guard).
- `orders` table gained `created_by_user_id` and `channel` ('pos' / 'manual' / 'shopify') columns.
- `app.py` now shows a login form first, then builds the sidebar navigation dynamically based on
  the logged-in user's role (`st.navigation`) — a role only ever sees pages it's allowed to open.
- Every existing page also has its own `require_role(...)` guard as a second layer of protection,
  so a direct URL visit to a page is blocked even if it isn't in that role's sidebar.
- The Invoicing page's PDF builder was extracted into `utils/pdf.py` so POS and Invoicing share
  one implementation instead of two copies.
- Added `bcrypt` to `requirements.txt`.
