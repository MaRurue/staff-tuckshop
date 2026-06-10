import streamlit as st
import pandas as pd
import os
import json
import requests
from datetime import datetime
import streamlit.components.v1 as components

# Set page config
st.set_page_config(
    page_title="Falcon Staff Purchasing App",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper to load CSS
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Inline CSS (dark-mode safe variables + blue theme overrides) ───────────────
st.markdown("""
<style>
/* ---- cart / sidebar elements ---- */
.cart-header {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-color);
    margin-bottom: 8px;
}
.cart-item {
    padding: 8px 0;
    border-bottom: 1px solid var(--secondary-background-color);
}
.cart-item-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text-color);
}
.cart-item-details {
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    color: var(--text-color);
    opacity: 0.8;
}
.cart-total {
    display: flex;
    justify-content: space-between;
    font-weight: 700;
    font-size: 1rem;
    color: var(--text-color);
    margin-top: 10px;
    padding-top: 8px;
    border-top: 2px solid var(--secondary-background-color);
}

/* ---- product cards ---- */
.product-title {
    font-weight: 700;
    font-size: 0.95rem;
    color: var(--text-color);
    margin-bottom: 2px;
}
.product-meta {
    font-size: 0.78rem;
    color: var(--text-color);
    opacity: 0.65;
    margin-bottom: 4px;
}
.product-price {
    font-size: 1.1rem;
    font-weight: 700;
    color: #10b981;
    margin-bottom: 6px;
}

/* ---- seller portal stats ---- */
.stat-card {
    background-color: var(--secondary-background-color);
    border-radius: 10px;
    padding: 18px 16px;
    text-align: center;
    border: 1px solid rgba(128,128,128,0.15);
}
.stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--text-color);
}
.stat-label {
    font-size: 0.78rem;
    color: var(--text-color);
    opacity: 0.6;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ---- order status badges ---- */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-pending {
    background-color: rgba(234, 179, 8, 0.18);
    color: #ca8a04;
    border: 1px solid rgba(234, 179, 8, 0.35);
}
.badge-completed {
    background-color: rgba(16, 185, 129, 0.15);
    color: #059669;
    border: 1px solid rgba(16, 185, 129, 0.3);
}

/* ---- danger zone (clear orders) ---- */
.danger-zone {
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 10px;
    padding: 18px 20px;
    background-color: rgba(239, 68, 68, 0.05);
    margin-top: 32px;
}
.danger-zone-title {
    font-weight: 700;
    font-size: 1rem;
    color: #ef4444;
    margin-bottom: 6px;
}
.danger-zone-desc {
    font-size: 0.85rem;
    color: var(--text-color);
    opacity: 0.7;
    margin-bottom: 14px;
}
</style>
""", unsafe_allow_html=True)

# Load custom styles
load_css("style.css")

# ── Constants ──────────────────────────────────────────────────────────────────
ORDERS_DIR = "orders"
OVERRIDES_FILE = "product_overrides.json"
os.makedirs(ORDERS_DIR, exist_ok=True)
LOGO_PATH = "falconlogo blue.jpg"

# Google Sheets Configuration
DEFAULT_GSHEETS_URL = "https://script.google.com/macros/s/AKfycbzKRy6fdEWiIll9V3zX-jgJIcsiknRB3-ITUIXaJEMfvbjRGSpjsIE69nJ156ONJIRp/exec"
GSHEETS_WEBAPP_URL = st.secrets.get("GSHEETS_WEBAPP_URL", DEFAULT_GSHEETS_URL)


# ── Product overrides (local persistence for admin-added / edited items) ───────

def load_product_overrides():
    """Returns dict: {sheet_name: [{Product, UOM, Cost price}, ...]}"""
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
    """
    Merge overrides into the loaded product data.
    - Price edits update existing rows in-place.
    - New rows (product name not in sheet) are appended.
    """
    import copy
    result = copy.deepcopy(data)

    for sheet_name, rows in overrides.items():
        if sheet_name not in result:
            # Brand-new category sheet from admin
            result[sheet_name] = pd.DataFrame(rows, columns=["Product", "UOM", "Cost price"])
        else:
            df = result[sheet_name].copy()
            for row in rows:
                mask = df["Product"] == row["Product"]
                if mask.any():
                    df.loc[mask, "Cost price"] = float(row["Cost price"])
                    df.loc[mask, "UOM"] = row["UOM"]
                else:
                    new_row = pd.DataFrame([{
                        "Product": row["Product"],
                        "UOM": row["UOM"],
                        "Cost price": float(row["Cost price"])
                    }])
                    df = pd.concat([df, new_row], ignore_index=True)
            result[sheet_name] = df.sort_values("Product").reset_index(drop=True)
    return result


# ── Order data functions ───────────────────────────────────────────────────────

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
            r = requests.post(GSHEETS_WEBAPP_URL, json={"action": "update_status", "order_id": order_id, "status": status}, timeout=10)
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
    """Delete every row in the Orders sheet (keeps header) and wipe local JSON files."""
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
    """Delete specific orders by their order_id from cloud and local storage."""
    cloud_ok = False
    if GSHEETS_WEBAPP_URL:
        try:
            r = requests.post(
                GSHEETS_WEBAPP_URL,
                json={"action": "delete_selected", "order_ids": order_ids},
                timeout=15
            )
            if r.status_code == 200:
                resp = r.json()
                cloud_ok = resp.get("success", False)
        except Exception:
            pass

    # Always wipe local copies
    for oid in order_ids:
        fp = os.path.join(ORDERS_DIR, f"order_{oid}.json")
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass
    return cloud_ok


# ── Product data loading ───────────────────────────────────────────────────────

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


# ── Product data source ────────────────────────────────────────────────────────
PRODUCTS_URL = st.secrets.get("PRODUCTS_GOOGLE_SHEET_URL", None)
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
    uploaded_file = st.file_uploader("📂 Upload the tuckshop products Excel workbook:", type=["xlsx"])
    if uploaded_file is not None:
        import io
        data, load_error = load_data_from_excel(io.BytesIO(uploaded_file.read()))
    else:
        st.info("⏳ Waiting for Excel workbook — or set PRODUCTS_GOOGLE_SHEET_URL in Streamlit Secrets.")
        st.stop()

if load_error:
    st.error(f"Error loading Excel workbook: {load_error}")
    st.stop()
if data is None:
    st.info("Waiting for product data...")
    st.stop()

# Apply any admin overrides
overrides = load_product_overrides()
data = apply_overrides(data, overrides)

# ── Session state ──────────────────────────────────────────────────────────────
for key, default in [
    ("quantities", {}),
    ("order_placed", False),
    ("latest_order", None),
    ("seller_authenticated", False),
    ("confirm_clear", False),
    ("confirm_delete_selected", False),
    ("orders_to_delete", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def clear_cart():
    st.session_state.quantities = {}
    st.session_state.order_placed = False
    st.session_state.latest_order = None


def logout_seller():
    st.session_state.seller_authenticated = False
    st.session_state.confirm_clear = False
    st.session_state.confirm_delete_selected = False
    st.session_state.orders_to_delete = []


# ── Receipt HTML helper ────────────────────────────────────────────────────────
def generate_receipt_html_helper(order, items_rows):
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
.print-btn:hover{{background:#1d4ed8;}}
@media print{{.print-btn-container{{display:none;}}.receipt-container{{border:none;padding:0;margin:0;max-width:100%;}}}}
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


# ── Logo helper ────────────────────────────────────────────────────────────────
def show_logo(width=80):
    if os.path.exists(LOGO_PATH):
        col_logo, col_title = st.columns([1, 6])
        with col_logo:
            st.image(LOGO_PATH, width=width)
        with col_title:
            st.markdown(
                "<div style='padding-top:10px;'>"
                "<span style='font-size:1.6rem;font-weight:800;color:#1e3a8a;'>FALCON COLLEGE</span><br>"
                "<span style='font-size:0.85rem;color:#3b82f6;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;'>"
                "Tuckshop Staff Ordering Portal</span></div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            "<h2 style='color:#1e3a8a;margin:0;'>🦅 FALCON COLLEGE — Tuckshop Staff Ordering Portal</h2>",
            unsafe_allow_html=True
        )


# ── Navigation ─────────────────────────────────────────────────────────────────
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=70)
    st.markdown("<div class='cart-header'>🦅 Falcon College Tuckshop</div>", unsafe_allow_html=True)
    app_mode = st.selectbox("Select View Mode", ["🛒 Staff Storefront", "🔑 Seller Portal"], label_visibility="collapsed")
    db_status = "gspread" if GSHEETS_WEBAPP_URL else "local"
    if db_status == "gspread":
        st.markdown("<div style='text-align:center;color:#10b981;font-size:0.85rem;font-weight:bold;margin-top:10px;'>🟢 Cloud Connected</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='text-align:center;color:#f59e0b;font-size:0.85rem;font-weight:bold;margin-top:10px;'>🟡 Offline / Local Mode</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STAFF STOREFRONT
# ══════════════════════════════════════════════════════════════════════════════
if app_mode == "🛒 Staff Storefront":
    # ── Sidebar: Cart with per-item checkboxes ─────────────────────────────────
    with st.sidebar:
        st.markdown("<div class='cart-header'>🛒 Your Cart</div>", unsafe_allow_html=True)
        if not cart_items:
            st.write("Your cart is empty. Add items from the catalog.")
        else:
            # Track which items to keep (checkbox checked = keep)
            keep_flags = {}
            for item in cart_items:
                keep_flags[item["key"]] = st.checkbox(
                    f"**{item['name']}**  \n{item['qty']} × ${item['price']:.2f} ({item['uom']}) = **${item['subtotal']:.2f}**",
                    value=True,
                    key=f"cart_cb_{item['key']}"
                )

            st.markdown(f"""
            <div class='cart-total'>
                <span>TOTAL DUE:</span><span>${cart_total:.2f}</span>
            </div>""", unsafe_allow_html=True)

            col_remove, col_clear = st.columns(2)
            with col_remove:
                if st.button("➖ Remove Unchecked", use_container_width=True):
                    for item in cart_items:
                        if not keep_flags.get(item["key"], True):
                            if item["key"] in st.session_state.quantities:
                                del st.session_state.quantities[item["key"]]
                    st.rerun()
            with col_clear:
                st.button("🧹 Clear All", on_click=clear_cart, use_container_width=True)

            st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
            st.markdown("<div class='cart-header'>📋 Checkout Details</div>", unsafe_allow_html=True)
            staff_name = st.text_input("Full Name", placeholder="e.g. John Doe")
            staff_id = st.text_input("Staff ID / Department", placeholder="e.g. ENG-402")
            if st.button("Place Order & Get Receipt", type="primary", use_container_width=True):
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
                    st.success("Order processed successfully!")
                    st.rerun()

    # ── Main area ──────────────────────────────────────────────────────────────
    show_logo()
    st.markdown("<p style='text-align:center;color:#64748b;font-size:1.05rem;margin-bottom:28px;'>Select items from the catalog below. Enter checkout details in the sidebar and print your receipt.</p>", unsafe_allow_html=True)
    st.divider()

    if st.session_state.order_placed and st.session_state.latest_order:
        order = st.session_state.latest_order
        st.balloons()
        st.markdown("<h3 style='text-align:center;'>🎉 Order Successfully Placed!</h3>", unsafe_allow_html=True)
        st.markdown("Please print the receipt below and present it to the tuckshop to collect your order.")
        items_rows = "".join(
            f"<tr><td>{i['name']}<br><small>{i['uom']} @ ${i['price']:.2f}</small></td>"
            f"<td style='text-align:center;'>{i['qty']}</td>"
            f"<td style='text-align:right;'>${i['subtotal']:.2f}</td></tr>"
            for i in order["items"]
        )
        components.html(generate_receipt_html_helper(order, items_rows), height=550, scrolling=True)
        st.button("🔄 Back to Tuckshop / Order More", on_click=clear_cart)

    else:
        search_query = st.text_input("🔍 Search tuckshop items...", "").strip().lower()

        def render_product_card(category, row, idx, key_prefix=""):
            """Render a single product card with ➖ / number_input / ➕ controls."""
            pk = f"{category}|||{row['Product']}|||{row['UOM']}|||{row['Cost price']}"
            cq = st.session_state.quantities.get(pk, 0)
            with st.container(border=True):
                st.markdown(f"<div class='product-title'>{row['Product']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='product-meta'>Category: {category} | UOM: {row['UOM']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='product-price'>${row['Cost price']:.2f}</div>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    if st.button("➖", key=f"d_{key_prefix}{pk}_{idx}"):
                        if cq > 0:
                            st.session_state.quantities[pk] = cq - 1
                            st.rerun()
                with c2:
                    new_qty = st.number_input(
                        "Qty",
                        min_value=0,
                        value=cq,
                        step=1,
                        label_visibility="collapsed",
                        key=f"ni_{key_prefix}{pk}_{idx}"
                    )
                    if new_qty != cq:
                        st.session_state.quantities[pk] = new_qty
                        st.rerun()
                with c3:
                    if st.button("➕", key=f"i_{key_prefix}{pk}_{idx}"):
                        st.session_state.quantities[pk] = cq + 1
                        st.rerun()

        if search_query:
            st.markdown(f"### Search Results for *\"{search_query}\"*")
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


# ══════════════════════════════════════════════════════════════════════════════
# SELLER PORTAL
# ══════════════════════════════════════════════════════════════════════════════
elif app_mode == "🔑 Seller Portal":
    show_logo()
    st.markdown("<p style='text-align:center;color:#64748b;font-size:1.05rem;margin-bottom:28px;'>Admin portal — manage orders, products, and pricing.</p>", unsafe_allow_html=True)
    st.divider()

    if not st.session_state.seller_authenticated:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            with st.container(border=True):
                st.markdown("<h3 style='text-align:center;margin-bottom:20px;'>Seller Sign In</h3>", unsafe_allow_html=True)
                password = st.text_input("Enter Seller Password", type="password")
                if st.button("Unlock Admin Panel", type="primary", use_container_width=True):
                    if password == "sales123":
                        st.session_state.seller_authenticated = True
                        st.success("Access Granted!")
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please try again.")
    else:
        orders, db_source = load_orders()

        with st.sidebar:
            st.markdown("<div class='cart-header'>⚙️ Admin Session</div>", unsafe_allow_html=True)
            if db_source == "gspread":
                st.markdown("<div style='color:#10b981;font-size:0.9rem;font-weight:bold;margin-bottom:15px;'>🟢 Cloud Sync Active</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color:#f59e0b;font-size:0.9rem;font-weight:bold;margin-bottom:15px;'>🟡 Local Fallback Mode</div>", unsafe_allow_html=True)
            st.button("🔄 Refresh Orders", use_container_width=True)
            st.button("🔒 Lock Portal / Log Out", on_click=logout_seller, use_container_width=True)

        # ── Stats ──────────────────────────────────────────────────────────────
        total_orders = len(orders)
        total_revenue = sum(o.get("total", 0.0) for o in orders)
        pending_orders = sum(1 for o in orders if o.get("status") == "Pending")
        completed_orders = sum(1 for o in orders if o.get("status") == "Completed")

        c1, c2, c3, c4 = st.columns(4)
        for col, val, label, color in [
            (c1, total_orders, "Total Orders", "var(--text-color)"),
            (c2, f"${total_revenue:.2f}", "Total Revenue", "var(--text-color)"),
            (c3, pending_orders, "Pending", "#d97706"),
            (c4, completed_orders, "Completed", "#059669"),
        ]:
            with col:
                st.markdown(f"""
                <div class='stat-card'>
                    <div class='stat-value' style='color:{color};'>{val}</div>
                    <div class='stat-label'>{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)

        # ── Portal Tabs ────────────────────────────────────────────────────────
        portal_tab_orders, portal_tab_products = st.tabs(["📋 Orders", "🗂️ Manage Products"])

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1 — ORDERS
        # ══════════════════════════════════════════════════════════════════════
        with portal_tab_orders:
            filter_status = st.radio("Filter Orders by Status:", ["All", "Pending", "Completed"], horizontal=True)
            filtered_orders = [o for o in orders if filter_status == "All" or o.get("status") == filter_status]
            st.markdown(f"### Receipts list ({len(filtered_orders)} orders)")

            if not filtered_orders:
                st.info("No orders found matching the selected filter.")
            else:
                # ── Per-order checkboxes for selective deletion ───────────────
                selected_order_ids = []
                for idx, order in enumerate(filtered_orders):
                    badge_class = "badge-pending" if order["status"] == "Pending" else "badge-completed"
                    with st.container(border=True):
                        col_cb, col_info, col_toggle = st.columns([0.3, 3, 1])
                        with col_cb:
                            is_selected = st.checkbox(
                                "Select",
                                key=f"sel_{order['order_id']}_{idx}",
                                label_visibility="collapsed"
                            )
                            if is_selected:
                                selected_order_ids.append(order["order_id"])
                        with col_info:
                            st.markdown(f"""
                            <div style='display:flex;align-items:center;gap:15px;margin-bottom:6px;'>
                                <span style='font-size:1.1rem;font-weight:700;color:var(--text-color);'>Order #{order['order_id']}</span>
                                <span class='badge {badge_class}'>{order['status']}</span>
                            </div>
                            <div style='font-size:0.9rem;color:var(--text-color);opacity:0.85;'>
                                <strong>Staff:</strong> {order['staff_name']} ({order['staff_id']}) &nbsp;|&nbsp;
                                <strong>Date:</strong> {order['date']} &nbsp;|&nbsp;
                                <strong>Total:</strong> <strong style='color:#10b981;'>${order['total']:.2f}</strong>
                            </div>""", unsafe_allow_html=True)
                        with col_toggle:
                            if order["status"] == "Pending":
                                if st.button("Mark Completed ✅", key=f"complete_{order['order_id']}_{idx}", use_container_width=True):
                                    if update_order_status(order["order_id"], "Completed"):
                                        st.success(f"Order #{order['order_id']} marked as completed!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to update status. Please try again.")
                            else:
                                if st.button("Mark Pending ⏳", key=f"pending_{order['order_id']}_{idx}", use_container_width=True):
                                    if update_order_status(order["order_id"], "Pending"):
                                        st.success(f"Order #{order['order_id']} marked as pending.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to update status. Please try again.")
                        with st.expander("🔍 View Items / Print Receipt"):
                            table_md = "| Product | Category | UOM | Qty | Cost | Subtotal |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"
                            for item in order["items"]:
                                table_md += f"| {item['name']} | {item['category']} | {item['uom']} | {item['qty']} | ${item['price']:.2f} | ${item['subtotal']:.2f} |\n"
                            st.markdown(table_md)
                            if st.toggle("Show printable receipt format", key=f"pt_{order['order_id']}_{idx}"):
                                items_rows = "".join(
                                    f"<tr><td>{i['name']}<br><small>{i['uom']} @ ${i['price']:.2f}</small></td>"
                                    f"<td style='text-align:center;'>{i['qty']}</td>"
                                    f"<td style='text-align:right;'>${i['subtotal']:.2f}</td></tr>"
                                    for i in order["items"]
                                )
                                components.html(generate_receipt_html_helper(order, items_rows), height=450, scrolling=True)

                # ── Delete Selected ───────────────────────────────────────────
                st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
                if selected_order_ids:
                    st.info(f"**{len(selected_order_ids)}** order(s) selected for deletion.")
                    if not st.session_state.confirm_delete_selected:
                        if st.button(f"🗑️ Delete {len(selected_order_ids)} Selected Order(s)", type="secondary"):
                            st.session_state.orders_to_delete = selected_order_ids
                            st.session_state.confirm_delete_selected = True
                            st.rerun()
                    else:
                        st.warning(f"⚠️ Are you sure you want to permanently delete **{len(st.session_state.orders_to_delete)}** order(s)? This cannot be undone.")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Yes, delete selected", type="primary", use_container_width=True):
                                with st.spinner("Deleting orders..."):
                                    cloud_ok = delete_orders_by_ids(st.session_state.orders_to_delete)
                                st.session_state.confirm_delete_selected = False
                                st.session_state.orders_to_delete = []
                                if cloud_ok:
                                    st.success("Selected orders deleted from Google Sheets and local storage.")
                                else:
                                    st.warning("Local orders deleted. Cloud sync may need the updated Apps Script — check the plan for the snippet.")
                                st.rerun()
                        with col_no:
                            if st.button("❌ Cancel", use_container_width=True):
                                st.session_state.confirm_delete_selected = False
                                st.session_state.orders_to_delete = []
                                st.rerun()

            # ── Danger Zone: Clear All Orders ─────────────────────────────────
            st.markdown("""
            <div class='danger-zone'>
                <div class='danger-zone-title'>⚠️ Danger Zone</div>
                <div class='danger-zone-desc'>
                    Permanently deletes <strong>all orders</strong> from Google Sheets and local storage.
                    Use this to wipe test data before going live. This cannot be undone.
                </div>
            </div>""", unsafe_allow_html=True)

            if not st.session_state.confirm_clear:
                if st.button("🗑️ Clear All Orders", type="secondary"):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning("Are you sure? This will permanently delete every order.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ Yes, delete everything", type="primary", use_container_width=True):
                        with st.spinner("Clearing orders..."):
                            cloud_ok = clear_all_orders()
                        st.session_state.confirm_clear = False
                        if cloud_ok:
                            st.success("All orders cleared from Google Sheets and local storage.")
                        else:
                            st.warning("Local orders cleared. Cloud sync may not have completed — check the Orders tab in your sheet.")
                        st.rerun()
                with col_no:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.confirm_clear = False
                        st.rerun()

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2 — MANAGE PRODUCTS
        # ══════════════════════════════════════════════════════════════════════
        with portal_tab_products:
            st.markdown("### 🗂️ Product Catalogue Management")
            st.markdown(
                "Add new items or update prices here. Changes are saved to a local override file "
                "and applied immediately on all sessions after the next page refresh. "
                "The source Excel / Google Sheet is never modified."
            )
            st.info("💡 Price edits take effect immediately for new orders. Existing orders are not affected.")

            # ── Add New Product ────────────────────────────────────────────────
            with st.expander("➕ Add a New Product", expanded=False):
                all_categories = list(data.keys())
                col_a, col_b = st.columns(2)
                with col_a:
                    new_category = st.selectbox("Category (Sheet)", all_categories + ["+ Create New Category"], key="new_prod_cat")
                    if new_category == "+ Create New Category":
                        new_category = st.text_input("New Category Name", key="new_cat_name").strip()
                    new_product_name = st.text_input("Product Name", key="new_prod_name").strip()
                with col_b:
                    new_uom = st.text_input("Unit of Measure (UOM)", placeholder="e.g. Each, kg, 500ml", key="new_prod_uom").strip()
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
                        # Check for duplicates
                        existing = [r for r in cat_rows if r["Product"].lower() == new_product_name.lower()]
                        if existing:
                            st.warning(f"'{new_product_name}' already exists in '{new_category}'. Use the edit section below to update its price.")
                        else:
                            cat_rows.append({
                                "Product": new_product_name,
                                "UOM": new_uom,
                                "Cost price": new_price
                            })
                            ov[new_category] = cat_rows
                            if save_product_overrides(ov):
                                st.success(f"✅ '{new_product_name}' added to '{new_category}' at ${new_price:.2f}. Refresh the storefront to see it.")
                                st.cache_data.clear()
                            else:
                                st.error("Failed to save product. Check file write permissions.")

            # ── Edit Existing Prices ───────────────────────────────────────────
            st.markdown("#### ✏️ Edit Product Prices")
            st.markdown("Select a category to see all products and update their prices.")
            selected_edit_cat = st.selectbox("Category to Edit", list(data.keys()), key="edit_cat_select")

            if selected_edit_cat:
                df_edit = data[selected_edit_cat].reset_index(drop=True)
                current_overrides = load_product_overrides()
                override_lookup = {
                    r["Product"]: r for r in current_overrides.get(selected_edit_cat, [])
                }

                st.markdown(f"**{len(df_edit)} products in '{selected_edit_cat}'**")
                changes_made = {}

                # Show in groups of columns for compactness
                for idx, row in df_edit.iterrows():
                    product_name = row["Product"]
                    current_price = float(row["Cost price"])
                    current_uom = str(row["UOM"])

                    with st.container(border=False):
                        e1, e2, e3, e4 = st.columns([3, 2, 2, 1])
                        with e1:
                            st.markdown(f"**{product_name}**  \n<span style='color:#64748b;font-size:0.8rem;'>{current_uom}</span>", unsafe_allow_html=True)
                        with e2:
                            new_uom_edit = st.text_input(
                                "UOM", value=current_uom,
                                key=f"edit_uom_{selected_edit_cat}_{idx}",
                                label_visibility="collapsed"
                            )
                        with e3:
                            new_price_edit = st.number_input(
                                "Price", value=current_price,
                                min_value=0.0, step=0.10, format="%.2f",
                                key=f"edit_price_{selected_edit_cat}_{idx}",
                                label_visibility="collapsed"
                            )
                        with e4:
                            if st.button("💾", key=f"save_edit_{selected_edit_cat}_{idx}", help="Save this price"):
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
                                    cat_rows.append({
                                        "Product": product_name,
                                        "UOM": new_uom_edit,
                                        "Cost price": new_price_edit
                                    })
                                ov[selected_edit_cat] = cat_rows
                                if save_product_overrides(ov):
                                    st.success(f"✅ '{product_name}' → ${new_price_edit:.2f}")
                                    st.cache_data.clear()
                                else:
                                    st.error("Save failed.")

                    st.divider()

                # ── Remove an Override (restore original price) ─────────────
                if current_overrides.get(selected_edit_cat):
                    st.markdown("##### 🔄 Restore Original Prices")
                    override_names = [r["Product"] for r in current_overrides.get(selected_edit_cat, [])]
                    restore_product = st.selectbox("Select product to restore to original Excel price", override_names, key="restore_select")
                    if st.button("↩️ Restore Original Price", key="btn_restore"):
                        ov = load_product_overrides()
                        ov[selected_edit_cat] = [r for r in ov.get(selected_edit_cat, []) if r["Product"] != restore_product]
                        if not ov[selected_edit_cat]:
                            del ov[selected_edit_cat]
                        if save_product_overrides(ov):
                            st.success(f"✅ '{restore_product}' restored to original Excel price.")
                            st.cache_data.clear()
                        else:
                            st.error("Restore failed.")