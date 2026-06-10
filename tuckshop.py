import streamlit as st
import pandas as pd
import os
import json
import requests
from datetime import datetime
import streamlit.components.v1 as components

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Falcon College Tuckshop",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Constants ──────────────────────────────────────────────────────────────────
ORDERS_DIR = "orders"
OVERRIDES_FILE = "product_overrides.json"
os.makedirs(ORDERS_DIR, exist_ok=True)
LOGO_PATH = "falconlogo blue.jpg"

# Google Sheets — hardcoded URL (no secrets needed)
GSHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbw0Cjo1K_cR69c3ukF4YwhtuNdQEkupwHZKNgPlH3tEnQWKS8vQdPN2BxE6s1QN5xDa/exec"

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="collapsedControl"] { display: none; }

/* ── Remove default sidebar completely ── */
[data-testid="stSidebar"] { display: none !important; }

/* ── Root spacing to make room for fixed top bar + bottom cart ── */
.main .block-container {
    padding-top: 90px !important;
    padding-bottom: 200px !important;
    max-width: 1200px;
}

/* ══════════════════════════════════════
   TOP NAV BAR
══════════════════════════════════════ */
.top-nav {
    position: fixed;
    top: 0; left: 0; right: 0;
    z-index: 1000;
    background: #0f1b35;
    border-bottom: 2px solid #1e3f7a;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 28px;
    height: 62px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.35);
}
.top-nav-brand {
    display: flex;
    align-items: center;
    gap: 14px;
}
.top-nav-logo {
    width: 38px;
    height: 38px;
    background: #2563eb;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 1rem;
    color: #fff;
    letter-spacing: -0.5px;
    flex-shrink: 0;
}
.top-nav-title {
    line-height: 1.15;
}
.top-nav-title .main-title {
    font-size: 1rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.top-nav-title .sub-title {
    font-size: 0.72rem;
    color: #60a5fa;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
.top-nav-right {
    display: flex;
    align-items: center;
    gap: 10px;
}
.top-nav-right .db-status {
    font-size: 0.78rem;
    color: #94a3b8;
    margin-right: 6px;
}
.top-nav-right .db-status .dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #10b981;
    margin-right: 5px;
    vertical-align: middle;
}

/* Nav mode buttons rendered via st.button — we style via CSS */
.stButton > button {
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 6px 18px !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
}

/* ══════════════════════════════════════
   BOTTOM CART BAR
══════════════════════════════════════ */
.cart-bar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    z-index: 1000;
    background: #fff;
    border-top: 2px solid #dbeafe;
    box-shadow: 0 -4px 24px rgba(37,99,235,0.10);
    padding: 0 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 68px;
}
.cart-bar-left {
    display: flex;
    align-items: center;
    gap: 16px;
}
.cart-bar-icon {
    font-size: 1.4rem;
}
.cart-bar-label {
    font-size: 1rem;
    font-weight: 700;
    color: #1e3a8a;
}
.cart-bar-count {
    background: #dbeafe;
    color: #1e3a8a;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.82rem;
    font-weight: 700;
}
.cart-bar-total {
    font-size: 1.1rem;
    font-weight: 800;
    color: #2563eb;
}
.cart-bar-empty {
    font-size: 0.85rem;
    color: #94a3b8;
    font-style: italic;
}

/* ══════════════════════════════════════
   PRODUCT CARDS
══════════════════════════════════════ */
.product-card {
    background: #fff;
    border: 1.5px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 14px 14px;
    margin-bottom: 4px;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.product-card:hover {
    border-color: #93c5fd;
    box-shadow: 0 2px 12px rgba(37,99,235,0.08);
}
.product-title {
    font-weight: 700;
    font-size: 0.92rem;
    color: #1e293b;
    margin-bottom: 3px;
    line-height: 1.3;
}
.product-meta {
    font-size: 0.76rem;
    color: #94a3b8;
    margin-bottom: 6px;
}
.product-price {
    font-size: 1.1rem;
    font-weight: 800;
    color: #10b981;
    margin-bottom: 8px;
}

/* ══════════════════════════════════════
   STAT CARDS
══════════════════════════════════════ */
.stat-card {
    background: #f8fafc;
    border: 1.5px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
}
.stat-value {
    font-size: 2rem;
    font-weight: 800;
    color: #1e293b;
}
.stat-label {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-top: 4px;
}

/* ══════════════════════════════════════
   BADGES
══════════════════════════════════════ */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
}
.badge-pending {
    background: #fef3c7;
    color: #b45309;
    border: 1px solid #fde68a;
}
.badge-completed {
    background: #d1fae5;
    color: #047857;
    border: 1px solid #a7f3d0;
}

/* ══════════════════════════════════════
   CART EXPANDED PANEL (toggled)
══════════════════════════════════════ */
.cart-panel {
    position: fixed;
    bottom: 68px; left: 0; right: 0;
    z-index: 999;
    background: #fff;
    border-top: 1.5px solid #dbeafe;
    box-shadow: 0 -8px 32px rgba(37,99,235,0.12);
    max-height: 340px;
    overflow-y: auto;
    padding: 20px 28px 16px;
}

/* ── Danger zone ── */
.danger-zone {
    border: 1.5px solid rgba(239,68,68,0.3);
    border-radius: 12px;
    padding: 18px 20px;
    background: rgba(239,68,68,0.04);
    margin-top: 28px;
}

/* ── Section header ── */
.section-header {
    font-size: 1.3rem;
    font-weight: 800;
    color: #1e3a8a;
    margin-bottom: 6px;
}
.section-sub {
    font-size: 0.88rem;
    color: #64748b;
    margin-bottom: 20px;
}

/* ── Tab override for cleaner look ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f1f5f9;
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    padding: 7px 20px;
    font-weight: 600;
    font-size: 0.88rem;
}
.stTabs [aria-selected="true"] {
    background: #fff !important;
    color: #2563eb !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [
    ("quantities", {}),
    ("order_placed", False),
    ("latest_order", None),
    ("seller_authenticated", False),
    ("confirm_clear", False),
    ("confirm_delete_selected", False),
    ("orders_to_delete", []),
    ("app_mode", "storefront"),
    ("cart_expanded", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ══════════════════════════════════════════════════════════════════════════════
# FIXED TOP NAV (rendered as HTML + Streamlit buttons)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="top-nav">
  <div class="top-nav-brand">
    <div class="top-nav-logo">FC</div>
    <div class="top-nav-title">
      <div class="main-title">Falcon College — Tuckshop</div>
      <div class="sub-title">Staff Purchases Dashboard</div>
    </div>
  </div>
  <div class="top-nav-right">
    <span class="db-status"><span class="dot"></span>Google Sheets Active</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Mode toggle buttons — we render them using st.columns positioned at top right
# via a container trick
nav_col1, nav_col2, nav_col3 = st.columns([6, 1, 1])
with nav_col2:
    if st.button("🛒 Staff Storefront", use_container_width=True,
                 type="primary" if st.session_state.app_mode == "storefront" else "secondary"):
        st.session_state.app_mode = "storefront"
        st.rerun()
with nav_col3:
    if st.button("🔑 Seller Portal", use_container_width=True,
                 type="primary" if st.session_state.app_mode == "seller" else "secondary"):
        st.session_state.app_mode = "seller"
        st.rerun()

# Position the nav buttons inside the fixed bar via CSS injection
st.markdown("""
<style>
/* Pull the first row of columns up into the nav bar */
div[data-testid="stHorizontalBlock"]:first-of-type {
    position: fixed;
    top: 10px;
    right: 20px;
    z-index: 1001;
    width: auto !important;
    max-width: 380px;
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="stHorizontalBlock"]:first-of-type > div:first-child {
    display: none !important; /* hide the spacer column */
}
</style>
""", unsafe_allow_html=True)


# ── Helper functions ───────────────────────────────────────────────────────────

def load_product_overrides():
    if os.path.exists(OVERRIDES_FILE):
        try:
            with open(OVERRIDES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_product_overrides(overrides: dict):
    try:
        with open(OVERRIDES_FILE, "w") as f:
            json.dump(overrides, f, indent=2)
        return True
    except Exception:
        return False


def apply_overrides(data: dict, overrides: dict) -> dict:
    import copy
    result = copy.deepcopy(data)
    for sheet_name, rows in overrides.items():
        if sheet_name not in result:
            result[sheet_name] = pd.DataFrame(rows, columns=["Product", "UOM", "Cost price"])
        else:
            df = result[sheet_name].copy()
            for row in rows:
                mask = df["Product"] == row["Product"]
                if mask.any():
                    df.loc[mask, "Cost price"] = float(row["Cost price"])
                    df.loc[mask, "UOM"] = row["UOM"]
                else:
                    new_row = pd.DataFrame([{"Product": row["Product"], "UOM": row["UOM"],
                                             "Cost price": float(row["Cost price"])}])
                    df = pd.concat([df, new_row], ignore_index=True)
            result[sheet_name] = df.sort_values("Product").reset_index(drop=True)
    return result


def load_orders():
    if GSHEETS_WEBAPP_URL:
        try:
            response = requests.get(GSHEETS_WEBAPP_URL, timeout=10)
            if response.status_code == 200:
                orders = response.json()
                for order in orders:
                    items = order.get("items", [])
                    if isinstance(items, str):
                        try:
                            order["items"] = json.loads(items)
                        except Exception:
                            order["items"] = []
                    if "status" not in order:
                        order["status"] = "Pending"
                    try:
                        order["total"] = float(order.get("total", 0))
                    except (ValueError, TypeError):
                        order["total"] = 0.0
                orders.sort(key=lambda x: x.get("order_id", ""), reverse=True)
                return orders, "gspread"
        except Exception:
            pass
    orders = []
    if os.path.exists(ORDERS_DIR):
        for file_name in [f for f in os.listdir(ORDERS_DIR) if f.startswith("order_") and f.endswith(".json")]:
            try:
                with open(os.path.join(ORDERS_DIR, file_name)) as f:
                    o = json.load(f)
                    if "status" not in o:
                        o["status"] = "Pending"
                    orders.append(o)
            except Exception:
                pass
    orders.sort(key=lambda x: x.get("order_id", ""), reverse=True)
    return orders, "local"


def save_order(order_data):
    success = False
    if GSHEETS_WEBAPP_URL:
        try:
            payload = {
                "action": "create",
                "order_id": order_data["order_id"],
                "date": order_data["date"],
                "staff_name": order_data["staff_name"],
                "staff_id": order_data["staff_id"],
                "total": order_data["total"],
                "status": order_data["status"],
                "items": order_data["items"]
            }
            r = requests.post(GSHEETS_WEBAPP_URL, json=payload, timeout=10)
            if r.status_code == 200:
                success = True
        except Exception:
            pass
    try:
        with open(os.path.join(ORDERS_DIR, f"order_{order_data['order_id']}.json"), "w") as f:
            json.dump(order_data, f, indent=4)
        if not GSHEETS_WEBAPP_URL:
            success = True
    except Exception:
        pass
    return success


def update_order_status(order_id, status):
    success = False
    if GSHEETS_WEBAPP_URL:
        try:
            r = requests.post(GSHEETS_WEBAPP_URL,
                              json={"action": "update_status", "order_id": order_id, "status": status},
                              timeout=10)
            if r.status_code == 200:
                success = True
        except Exception:
            pass
    try:
        fp = os.path.join(ORDERS_DIR, f"order_{order_id}.json")
        if os.path.exists(fp):
            with open(fp) as f:
                od = json.load(f)
            od["status"] = status
            with open(fp, "w") as f:
                json.dump(od, f, indent=4)
            if not GSHEETS_WEBAPP_URL:
                success = True
    except Exception:
        pass
    return success


def clear_all_orders():
    cloud_ok = False
    if GSHEETS_WEBAPP_URL:
        try:
            r = requests.post(GSHEETS_WEBAPP_URL, json={"action": "clear_all"}, timeout=15)
            if r.status_code == 200:
                resp = r.json()
                cloud_ok = resp.get("success", False)
        except Exception:
            pass
    if os.path.exists(ORDERS_DIR):
        for fn in os.listdir(ORDERS_DIR):
            if fn.startswith("order_") and fn.endswith(".json"):
                try:
                    os.remove(os.path.join(ORDERS_DIR, fn))
                except Exception:
                    pass
    return cloud_ok


def delete_orders_by_ids(order_ids: list):
    cloud_ok = False
    if GSHEETS_WEBAPP_URL:
        try:
            r = requests.post(GSHEETS_WEBAPP_URL,
                              json={"action": "delete_selected", "order_ids": order_ids},
                              timeout=15)
            if r.status_code == 200:
                resp = r.json()
                cloud_ok = resp.get("success", False)
        except Exception:
            pass
    for oid in order_ids:
        fp = os.path.join(ORDERS_DIR, f"order_{oid}.json")
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
    return cloud_ok


@st.cache_data
def load_data_from_excel(source):
    try:
        xl = pd.ExcelFile(source)
        data = {}
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            df.columns = [str(c).strip() for c in df.columns]
            lc = {c.lower(): c for c in df.columns}
            product_col = lc.get('product') or lc.get('product name') or lc.get('item') or lc.get('name')
            cost_col = (lc.get('cost price') or lc.get('cost_price') or lc.get('costprice')
                        or lc.get('price') or lc.get('cost') or lc.get('unit price') or lc.get('selling price'))
            uom_col = lc.get('uom') or lc.get('unit') or lc.get('unit of measure') or lc.get('units')
            if not product_col or not cost_col:
                continue
            rename = {product_col: 'Product', cost_col: 'Cost price'}
            if uom_col:
                rename[uom_col] = 'UOM'
            df.rename(columns=rename, inplace=True)
            if 'UOM' not in df.columns:
                df['UOM'] = ''
            df = df.dropna(subset=['Product', 'Cost price'])
            df['Product'] = df['Product'].astype(str).str.strip()
            df['UOM'] = df['UOM'].astype(str).str.strip().fillna('')
            df['Cost price'] = pd.to_numeric(df['Cost price'], errors='coerce')
            df = df.dropna(subset=['Cost price'])
            df = df[df['Product'].str.len() > 0].sort_values('Product')
            if not df.empty:
                data[sheet] = df
        if not data:
            debug = " | ".join(f"Sheet '{s}': {list(xl.parse(s).columns[:10])}" for s in xl.sheet_names)
            return None, f"No valid product sheets found. Need 'Product' and 'Cost price' columns. Found: {debug}"
        return data, None
    except Exception as e:
        return None, str(e)


# ── Load product data ──────────────────────────────────────────────────────────
try:
    PRODUCTS_URL = st.secrets.get("PRODUCTS_GOOGLE_SHEET_URL", None)
except Exception:
    PRODUCTS_URL = None

excel_path = r"C:\Users\Chara RN\Downloads\Products For Staff Purchase.xlsx"
if not os.path.exists(excel_path):
    excel_path = r"C:\Users\Chara RN\Downloads\Products available for staff to purchase.xlsx"

data = None
load_error = None

if PRODUCTS_URL:
    try:
        import io
        resp = requests.get(PRODUCTS_URL, timeout=15)
        resp.raise_for_status()
        data, load_error = load_data_from_excel(io.BytesIO(resp.content))
    except Exception as e:
        load_error = str(e)
elif os.path.exists(excel_path):
    data, load_error = load_data_from_excel(excel_path)
else:
    uploaded_file = st.file_uploader("Upload the tuckshop products Excel workbook:", type=["xlsx"])
    if uploaded_file is not None:
        import io
        data, load_error = load_data_from_excel(io.BytesIO(uploaded_file.read()))
    else:
        st.info("⏳ Waiting for Excel workbook — upload one above or set PRODUCTS_GOOGLE_SHEET_URL in Streamlit Secrets.")
        st.stop()

if load_error:
    st.error(f"Error loading Excel workbook: {load_error}")
    st.stop()
if data is None:
    st.info("Waiting for product data...")
    st.stop()

overrides = load_product_overrides()
data = apply_overrides(data, overrides)


# ── Cart calculation ───────────────────────────────────────────────────────────
cart_items = []
cart_total = 0.0
for key, qty in list(st.session_state.quantities.items()):
    if qty > 0:
        parts = key.split("|||")
        if len(parts) == 4:
            category, name, uom, price_str = parts
            price = float(price_str)
            subtotal = price * qty
            cart_items.append({"key": key, "category": category, "name": name,
                                "uom": uom, "price": price, "qty": qty, "subtotal": subtotal})
            cart_total += subtotal
        else:
            del st.session_state.quantities[key]

cart_count = sum(i["qty"] for i in cart_items)


# ── Helpers ────────────────────────────────────────────────────────────────────
def clear_cart():
    st.session_state.quantities = {}
    st.session_state.order_placed = False
    st.session_state.latest_order = None
    st.session_state.cart_expanded = False
    for k in list(st.session_state.keys()):
        if k.startswith("ni_") or k.startswith("cart_cb_"):
            try:
                del st.session_state[k]
            except Exception:
                pass


def logout_seller():
    st.session_state.seller_authenticated = False
    st.session_state.confirm_clear = False
    st.session_state.confirm_delete_selected = False
    st.session_state.orders_to_delete = []


def generate_receipt_html(order, items_rows):
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
body{{font-family:'Space Mono',monospace;color:#000;background:#fff;margin:0;padding:10px;display:flex;flex-direction:column;align-items:center;}}
.receipt-container{{width:100%;max-width:380px;border:2px dashed #000;padding:20px;box-sizing:border-box;}}
.header{{text-align:center;margin-bottom:20px;}}
.title{{font-size:1.6rem;font-weight:700;margin:0;letter-spacing:1px;}}
.subtitle{{font-size:0.85rem;margin:5px 0 0;font-weight:bold;}}
.divider{{border-top:1px dashed #000;margin:15px 0;}}
.info-section{{font-size:0.85rem;line-height:1.4;margin-bottom:15px;}}
.receipt-table{{width:100%;border-collapse:collapse;font-size:0.85rem;}}
.receipt-table th{{border-bottom:1px solid #000;padding:5px 0;text-align:left;}}
.receipt-table td{{padding:6px 0;}}
.total-row{{font-size:1.2rem;font-weight:700;display:flex;justify-content:space-between;margin-top:10px;}}
.footer{{text-align:center;margin-top:25px;font-size:0.8rem;}}
.print-btn-container{{margin-bottom:20px;text-align:center;}}
.print-btn{{background:#2563eb;color:#fff;border:none;padding:10px 24px;font-family:'Space Mono',monospace;font-size:1rem;font-weight:bold;border-radius:6px;cursor:pointer;}}
@media print{{.print-btn-container{{display:none;}}}}
</style>
</head>
<body>
<div class="print-btn-container"><button class="print-btn" onclick="window.print()">🖨️ PRINT / SAVE RECEIPT</button></div>
<div class="receipt-container">
  <div class="header"><div class="title">FALCON COLLEGE</div><div class="subtitle">TUCKSHOP — STAFF ORDER RECEIPT</div></div>
  <div class="info-section">
    <strong>Order ID:</strong> {order["order_id"]}<br>
    <strong>Date:</strong> {order["date"]}<br>
    <strong>Staff Name:</strong> {order["staff_name"]}<br>
    <strong>Staff ID:</strong> {order["staff_id"]}
  </div>
  <div class="divider"></div>
  <table class="receipt-table">
    <thead><tr><th>ITEM</th><th style="text-align:center;width:50px;">QTY</th><th style="text-align:right;width:80px;">TOTAL</th></tr></thead>
    <tbody>{items_rows}</tbody>
  </table>
  <div class="divider"></div>
  <div class="total-row"><span>TOTAL:</span><span>${order["total"]:.2f}</span></div>
  <div class="divider"></div>
  <div class="footer">Thank you for your order!<br>Please present this receipt at the tuckshop to collect your items.</div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# STAFF STOREFRONT
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.app_mode == "storefront":

    if st.session_state.order_placed and st.session_state.latest_order:
        order = st.session_state.latest_order
        st.balloons()
        st.markdown("<div class='section-header' style='text-align:center;'>🎉 Order Successfully Placed!</div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#64748b;'>Print the receipt below and present it at the tuckshop to collect your items.</p>", unsafe_allow_html=True)
        items_rows = "".join(
            f"<tr><td>{i['name']}<br><small>{i['uom']} @ ${i['price']:.2f}</small></td>"
            f"<td style='text-align:center;'>{i['qty']}</td>"
            f"<td style='text-align:right;'>${i['subtotal']:.2f}</td></tr>"
            for i in order["items"]
        )
        components.html(generate_receipt_html(order, items_rows), height=560, scrolling=True)
        st.button("🔄 Back to Tuckshop / Order More", on_click=clear_cart, type="primary")

    else:
        # ── Page heading ──────────────────────────────────────────────────────
        st.markdown("<div class='section-header'>Browse the Tuckshop</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-sub'>Choose your items below. When you're ready, review your cart at the bottom of the page.</div>", unsafe_allow_html=True)

        search_query = st.text_input("🔍 Search items...", "", placeholder="e.g. juice, chips, bread").strip().lower()

        def render_product_card(category, row, idx, key_prefix=""):
            pk = f"{category}|||{row['Product']}|||{row['UOM']}|||{row['Cost price']}"
            cq = st.session_state.quantities.get(pk, 0)
            with st.container(border=True):
                st.markdown(f"<div class='product-title'>{row['Product']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='product-meta'>{category} · {row['UOM']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='product-price'>${row['Cost price']:.2f}</div>", unsafe_allow_html=True)
                new_qty = st.number_input(
                    "Qty", min_value=0, value=cq, step=1,
                    key=f"ni_{key_prefix}{pk}_{idx}",
                    label_visibility="collapsed"
                )
                if new_qty != cq:
                    if new_qty > 0:
                        st.session_state.quantities[pk] = new_qty
                    else:
                        st.session_state.quantities.pop(pk, None)
                    st.rerun()

        if search_query:
            st.markdown(f"##### Results for *\"{search_query}\"*")
            matches = [(cat, row) for cat, df in data.items()
                       for _, row in df.iterrows()
                       if search_query in str(row['Product']).lower() or search_query in str(row['UOM']).lower()]
            if not matches:
                st.info("No items found. Try a different search term.")
            else:
                cols = st.columns(3)
                for i, (category, row) in enumerate(matches):
                    with cols[i % 3]:
                        render_product_card(category, row, i, key_prefix="s_")
        else:
            tabs = st.tabs([f"📁 {s}" for s in data.keys()])
            for tab, (sheet, df) in zip(tabs, data.items()):
                with tab:
                    cols = st.columns(3)
                    for idx, row in df.reset_index(drop=True).iterrows():
                        with cols[idx % 3]:
                            render_product_card(sheet, row, idx, key_prefix="t_")

        # ── Cart expanded panel (shown above the bottom bar when toggled) ─────
        if st.session_state.cart_expanded and cart_items:
            with st.expander("🛒 Cart & Checkout", expanded=True):
                st.markdown("#### Items in Your Cart")
                keep_flags = {}
                for item in cart_items:
                    keep_flags[item["key"]] = st.checkbox(
                        f"**{item['name']}** — {item['qty']} × ${item['price']:.2f} = **${item['subtotal']:.2f}**  \n"
                        f"<span style='font-size:0.78rem;color:#94a3b8;'>{item['category']} · {item['uom']}</span>",
                        value=True,
                        key=f"cart_cb_{item['key']}"
                    )
                st.markdown(f"**Cart Total: ${cart_total:.2f}**")
                col_remove, col_clear = st.columns(2)
                with col_remove:
                    if st.button("Remove Unticked", use_container_width=True):
                        for item in cart_items:
                            if not keep_flags.get(item["key"], True):
                                st.session_state.quantities.pop(item["key"], None)
                                cb_key = f"cart_cb_{item['key']}"
                                if cb_key in st.session_state:
                                    del st.session_state[cb_key]
                        st.rerun()
                with col_clear:
                    st.button("Clear All", on_click=clear_cart, use_container_width=True)

                st.markdown("---")
                st.markdown("#### Checkout")
                staff_name = st.text_input("Your Full Name", placeholder="e.g. John Doe", key="checkout_name")
                staff_id = st.text_input("Staff ID / Department", placeholder="e.g. ENG-402", key="checkout_id")
                if st.button("✅ Place Order & Get Receipt", type="primary", use_container_width=True):
                    if not staff_name.strip():
                        st.error("Please enter your name.")
                    elif not staff_id.strip():
                        st.error("Please enter your Staff ID or Department.")
                    else:
                        order_id = datetime.now().strftime("%Y%m%d%H%M%S")
                        order_data = {
                            "order_id": order_id,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "staff_name": staff_name.strip(),
                            "staff_id": staff_id.strip(),
                            "status": "Pending",
                            "items": [{"category": i["category"], "name": i["name"], "uom": i["uom"],
                                       "price": i["price"], "qty": i["qty"], "subtotal": i["subtotal"]}
                                      for i in cart_items],
                            "total": cart_total
                        }
                        save_order(order_data)
                        st.session_state.latest_order = order_data
                        st.session_state.order_placed = True
                        st.success("Order processed!")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SELLER PORTAL
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.app_mode == "seller":

    if not st.session_state.seller_authenticated:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            with st.container(border=True):
                st.markdown("<div class='section-header' style='text-align:center;'>Seller Sign In</div>", unsafe_allow_html=True)
                st.markdown("<div class='section-sub' style='text-align:center;'>Enter your password to access the admin panel.</div>", unsafe_allow_html=True)
                password = st.text_input("Password", type="password", label_visibility="collapsed",
                                         placeholder="Enter seller password")
                if st.button("Unlock Admin Panel", type="primary", use_container_width=True):
                    if password == "sales123":
                        st.session_state.seller_authenticated = True
                        st.success("Access Granted!")
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please try again.")
    else:
        orders, db_source = load_orders()

        # ── Top controls ──────────────────────────────────────────────────────
        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([6, 1, 1])
        with ctrl_col1:
            st.markdown("<div class='section-header'>Seller Portal</div>", unsafe_allow_html=True)
            sync_label = "🟢 Cloud Sync Active" if db_source == "gspread" else "🟡 Local Fallback"
            st.markdown(f"<span style='font-size:0.85rem;color:#64748b;'>{sync_label}</span>", unsafe_allow_html=True)
        with ctrl_col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with ctrl_col3:
            st.button("🔒 Log Out", on_click=logout_seller, use_container_width=True)

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

        # ── Stats ─────────────────────────────────────────────────────────────
        total_orders = len(orders)
        total_revenue = sum(o.get("total", 0.0) for o in orders)
        pending_orders = sum(1 for o in orders if o.get("status") == "Pending")
        completed_orders = sum(1 for o in orders if o.get("status") == "Completed")

        c1, c2, c3, c4 = st.columns(4)
        for col, val, label, color in [
            (c1, total_orders, "Total Orders", "#1e293b"),
            (c2, f"${total_revenue:.2f}", "Total Revenue", "#1e293b"),
            (c3, pending_orders, "Pending", "#d97706"),
            (c4, completed_orders, "Completed", "#059669"),
        ]:
            with col:
                st.markdown(f"""
                <div class='stat-card'>
                    <div class='stat-value' style='color:{color};'>{val}</div>
                    <div class='stat-label'>{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

        # ── Portal tabs ───────────────────────────────────────────────────────
        portal_tab_orders, portal_tab_products = st.tabs(["📋 Orders", "🏷️ Manage Products"])

        # ── TAB 1: ORDERS ─────────────────────────────────────────────────────
        with portal_tab_orders:
            filter_status = st.radio("Filter:", ["All", "Pending", "Completed"], horizontal=True)
            filtered_orders = [o for o in orders if filter_status == "All" or o.get("status") == filter_status]
            st.markdown(f"**{len(filtered_orders)} orders**")

            if not filtered_orders:
                st.info("No orders found matching the selected filter.")
            else:
                selected_order_ids = []
                for idx, order in enumerate(filtered_orders):
                    badge_class = "badge-pending" if order["status"] == "Pending" else "badge-completed"
                    with st.container(border=True):
                        col_cb, col_info, col_toggle = st.columns([0.3, 3, 1])
                        with col_cb:
                            is_selected = st.checkbox("Select", key=f"sel_{order['order_id']}_{idx}",
                                                      label_visibility="collapsed")
                            if is_selected:
                                selected_order_ids.append(order["order_id"])
                        with col_info:
                            st.markdown(f"""
                            <div style='display:flex;align-items:center;gap:12px;margin-bottom:5px;'>
                                <span style='font-size:1rem;font-weight:700;color:#1e293b;'>Order #{order['order_id']}</span>
                                <span class='badge {badge_class}'>{order['status']}</span>
                            </div>
                            <div style='font-size:0.88rem;color:#64748b;'>
                                <strong style='color:#1e293b;'>{order['staff_name']}</strong> ({order['staff_id']}) &nbsp;·&nbsp;
                                {order['date']} &nbsp;·&nbsp;
                                <strong style='color:#10b981;'>${order['total']:.2f}</strong>
                            </div>""", unsafe_allow_html=True)
                        with col_toggle:
                            if order["status"] == "Pending":
                                if st.button("Mark Completed ✅", key=f"complete_{order['order_id']}_{idx}",
                                             use_container_width=True):
                                    if update_order_status(order["order_id"], "Completed"):
                                        st.success(f"Order #{order['order_id']} completed!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to update status.")
                            else:
                                if st.button("Mark Pending ⏳", key=f"pending_{order['order_id']}_{idx}",
                                             use_container_width=True):
                                    if update_order_status(order["order_id"], "Pending"):
                                        st.rerun()
                                    else:
                                        st.error("Failed to update status.")
                        with st.expander("🔍 View Items / Print Receipt"):
                            table_md = "| Product | Category | UOM | Qty | Price | Subtotal |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"
                            for item in order["items"]:
                                table_md += f"| {item['name']} | {item['category']} | {item['uom']} | {item['qty']} | ${item['price']:.2f} | ${item['subtotal']:.2f} |\n"
                            st.markdown(table_md)
                            if st.toggle("Show printable receipt", key=f"pt_{order['order_id']}_{idx}"):
                                items_rows = "".join(
                                    f"<tr><td>{i['name']}<br><small>{i['uom']} @ ${i['price']:.2f}</small></td>"
                                    f"<td style='text-align:center;'>{i['qty']}</td>"
                                    f"<td style='text-align:right;'>${i['subtotal']:.2f}</td></tr>"
                                    for i in order["items"]
                                )
                                components.html(generate_receipt_html(order, items_rows), height=450, scrolling=True)

                st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
                if selected_order_ids:
                    st.info(f"**{len(selected_order_ids)}** order(s) selected.")
                    if not st.session_state.confirm_delete_selected:
                        if st.button(f"🗑️ Delete {len(selected_order_ids)} Selected", type="secondary"):
                            st.session_state.orders_to_delete = selected_order_ids
                            st.session_state.confirm_delete_selected = True
                            st.rerun()
                    else:
                        st.warning(f"⚠️ Permanently delete **{len(st.session_state.orders_to_delete)}** order(s)? This cannot be undone.")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Confirm Delete", type="primary", use_container_width=True):
                                with st.spinner("Deleting..."):
                                    cloud_ok = delete_orders_by_ids(st.session_state.orders_to_delete)
                                st.session_state.confirm_delete_selected = False
                                st.session_state.orders_to_delete = []
                                st.success("Deleted." if cloud_ok else "Local deleted; cloud sync may be pending.")
                                st.rerun()
                        with col_no:
                            if st.button("❌ Cancel", use_container_width=True):
                                st.session_state.confirm_delete_selected = False
                                st.session_state.orders_to_delete = []
                                st.rerun()

            # Danger zone
            st.markdown("""
            <div class='danger-zone'>
                <div style='font-weight:700;font-size:0.95rem;color:#ef4444;margin-bottom:6px;'>⚠️ Danger Zone</div>
                <div style='font-size:0.84rem;color:#64748b;margin-bottom:12px;'>
                    Permanently delete <strong>all orders</strong> from Google Sheets and local storage.
                </div>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            if not st.session_state.confirm_clear:
                if st.button("🗑️ Clear All Orders", type="secondary"):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning("Are you sure? Every order will be permanently deleted.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes, delete everything", type="primary", use_container_width=True):
                        with st.spinner("Clearing..."):
                            cloud_ok = clear_all_orders()
                        st.session_state.confirm_clear = False
                        st.success("All orders cleared." if cloud_ok else "Local cleared; check Google Sheets.")
                        st.rerun()
                with col_no:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.confirm_clear = False
                        st.rerun()

        # ── TAB 2: MANAGE PRODUCTS ────────────────────────────────────────────
        with portal_tab_products:
            st.markdown("### 🏷️ Product Catalogue Management")
            st.info("Add new items or update prices here. Changes apply immediately. The source Excel is never modified.")

            with st.expander("➕ Add a New Product", expanded=False):
                all_categories = list(data.keys())
                col_a, col_b = st.columns(2)
                with col_a:
                    new_category = st.selectbox("Category", all_categories + ["+ Create New Category"], key="new_prod_cat")
                    if new_category == "+ Create New Category":
                        new_category = st.text_input("New Category Name", key="new_cat_name").strip()
                    new_product_name = st.text_input("Product Name", key="new_prod_name").strip()
                with col_b:
                    new_uom = st.text_input("Unit of Measure", placeholder="e.g. Each, kg", key="new_prod_uom").strip()
                    new_price = st.number_input("Price ($)", min_value=0.0, step=0.10, format="%.2f", key="new_prod_price")
                if st.button("💾 Add Product", type="primary", key="btn_add_product"):
                    if not new_product_name:
                        st.error("Product name cannot be empty.")
                    elif not new_category:
                        st.error("Category cannot be empty.")
                    elif new_price <= 0:
                        st.error("Price must be greater than $0.00.")
                    else:
                        ov = load_product_overrides()
                        cat_rows = ov.get(new_category, [])
                        existing = [r for r in cat_rows if r["Product"].lower() == new_product_name.lower()]
                        if existing:
                            st.warning(f"'{new_product_name}' already exists. Use the edit section to update its price.")
                        else:
                            cat_rows.append({"Product": new_product_name, "UOM": new_uom, "Cost price": new_price})
                            ov[new_category] = cat_rows
                            if save_product_overrides(ov):
                                st.success(f"✅ '{new_product_name}' added to '{new_category}' at ${new_price:.2f}.")
                                st.cache_data.clear()
                            else:
                                st.error("Failed to save. Check file write permissions.")

            st.markdown("#### ✏️ Edit Product Prices")
            selected_edit_cat = st.selectbox("Category to Edit", list(data.keys()), key="edit_cat_select")
            if selected_edit_cat:
                df_edit = data[selected_edit_cat].reset_index(drop=True)
                current_overrides = load_product_overrides()
                st.markdown(f"**{len(df_edit)} products in '{selected_edit_cat}'**")
                for idx, row in df_edit.iterrows():
                    product_name = row["Product"]
                    current_price = float(row["Cost price"])
                    current_uom = str(row["UOM"])
                    with st.container(border=False):
                        e1, e2, e3, e4 = st.columns([3, 2, 2, 1])
                        with e1:
                            st.markdown(f"**{product_name}**  \n<span style='color:#94a3b8;font-size:0.8rem;'>{current_uom}</span>", unsafe_allow_html=True)
                        with e2:
                            new_uom_edit = st.text_input("UOM", value=current_uom,
                                                         key=f"edit_uom_{selected_edit_cat}_{idx}",
                                                         label_visibility="collapsed")
                        with e3:
                            new_price_edit = st.number_input("Price", value=current_price, min_value=0.0,
                                                             step=0.10, format="%.2f",
                                                             key=f"edit_price_{selected_edit_cat}_{idx}",
                                                             label_visibility="collapsed")
                        with e4:
                            if st.button("💾", key=f"save_edit_{selected_edit_cat}_{idx}", help="Save"):
                                ov = load_product_overrides()
                                cat_rows = ov.get(selected_edit_cat, [])
                                updated = False
                                for r in cat_rows:
                                    if r["Product"] == product_name:
                                        r["Cost price"] = new_price_edit
                                        r["UOM"] = new_uom_edit
                                        updated = True
                                        break
                                if not updated:
                                    cat_rows.append({"Product": product_name, "UOM": new_uom_edit,
                                                     "Cost price": new_price_edit})
                                ov[selected_edit_cat] = cat_rows
                                if save_product_overrides(ov):
                                    st.success(f"✅ '{product_name}' → ${new_price_edit:.2f}")
                                    st.cache_data.clear()
                                else:
                                    st.error("Save failed.")
                    st.divider()

                if current_overrides.get(selected_edit_cat):
                    st.markdown("##### ↩️ Restore Original Prices")
                    override_names = [r["Product"] for r in current_overrides.get(selected_edit_cat, [])]
                    restore_product = st.selectbox("Select product to restore", override_names, key="restore_select")
                    if st.button("↩️ Restore Original Price", key="btn_restore"):
                        ov = load_product_overrides()
                        ov[selected_edit_cat] = [r for r in ov.get(selected_edit_cat, []) if r["Product"] != restore_product]
                        if not ov[selected_edit_cat]:
                            del ov[selected_edit_cat]
                        if save_product_overrides(ov):
                            st.success(f"✅ '{restore_product}' restored to original price.")
                            st.cache_data.clear()
                        else:
                            st.error("Restore failed.")


# ══════════════════════════════════════════════════════════════════════════════
# BOTTOM CART BAR (storefront only)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.app_mode == "storefront" and not st.session_state.order_placed:
    if cart_items:
        cart_bar_html = f"""
        <div class="cart-bar">
          <div class="cart-bar-left">
            <span class="cart-bar-icon">🛒</span>
            <span class="cart-bar-label">Your Cart</span>
            <span class="cart-bar-count">{cart_count} item{'s' if cart_count != 1 else ''}</span>
          </div>
          <span class="cart-bar-total">${cart_total:.2f}</span>
        </div>
        """
    else:
        cart_bar_html = """
        <div class="cart-bar">
          <div class="cart-bar-left">
            <span class="cart-bar-icon">🛒</span>
            <span class="cart-bar-label">Your Cart</span>
            <span class="cart-bar-count">0 items</span>
          </div>
          <span class="cart-bar-empty">Choose items from the catalog above to begin checking out.</span>
        </div>
        """
    st.markdown(cart_bar_html, unsafe_allow_html=True)

    # Toggle cart panel button — positioned via Streamlit
    if cart_items:
        toggle_label = "▾ Review Cart & Checkout" if not st.session_state.cart_expanded else "▴ Hide Cart"
        # Float this button above the cart bar
        st.markdown("""
        <style>
        /* Style the last button as a floating cart toggle */
        div[data-testid="stVerticalBlock"] > div:last-child .stButton > button {
            position: fixed;
            bottom: 72px;
            right: 28px;
            z-index: 1002;
            background: #2563eb;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 0.9rem;
            font-weight: 700;
            box-shadow: 0 4px 16px rgba(37,99,235,0.35);
        }
        div[data-testid="stVerticalBlock"] > div:last-child .stButton > button:hover {
            background: #1d4ed8;
        }
        </style>
        """, unsafe_allow_html=True)
        if st.button(toggle_label, key="cart_toggle_btn"):
            st.session_state.cart_expanded = not st.session_state.cart_expanded
            st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.app-footer {
    position: fixed;
    bottom: 68px;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 0.75rem;
    color: #cbd5e1;
    pointer-events: none;
    z-index: 998;
}
</style>
<div class="app-footer">Portal UTC: """ + datetime.utcnow().strftime("%Y-%m-%d %H:%M") + """ · Built by Chara</div>
""", unsafe_allow_html=True)
