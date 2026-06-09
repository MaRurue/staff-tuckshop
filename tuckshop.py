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

# Load custom styles
load_css("style.css")

# Ensure orders directory exists
ORDERS_DIR = "orders"
os.makedirs(ORDERS_DIR, exist_ok=True)

# Google Sheets Configuration
# Fallback to the deployment URL provided by the user
DEFAULT_GSHEETS_URL = "https://script.google.com/macros/s/AKfycbzKRy6fdEWiIll9V3zX-jgJIcsiknRB3-ITUIXaJEMfvbjRGSpjsIE69nJ156ONJIRp/exec"
GSHEETS_WEBAPP_URL = st.secrets.get("GSHEETS_WEBAPP_URL", DEFAULT_GSHEETS_URL)

def load_orders():
    """Load orders from Google Sheet Web App, falling back to local JSON files if configured/fails."""
    if GSHEETS_WEBAPP_URL:
        try:
            response = requests.get(GSHEETS_WEBAPP_URL, timeout=10)
            if response.status_code == 200:
                orders = response.json()
                orders.sort(key=lambda x: x.get("order_id", ""), reverse=True)
                return orders, "gspread"
        except Exception as e:
            pass  # Fail silently and fall back to local files
            
    # Fallback to local files
    orders = []
    if os.path.exists(ORDERS_DIR):
        order_files = [f for f in os.listdir(ORDERS_DIR) if f.startswith("order_") and f.endswith(".json")]
        for file_name in order_files:
            file_path = os.path.join(ORDERS_DIR, file_name)
            try:
                with open(file_path, "r") as f:
                    order_info = json.load(f)
                    if "status" not in order_info:
                        order_info["status"] = "Pending"
                    orders.append(order_info)
            except Exception as e:
                pass
    orders.sort(key=lambda x: x.get("order_id", ""), reverse=True)
    return orders, "local"

def save_order(order_data):
    """Save a new order. Writes to Google Sheet Web App if URL is configured, else local JSON."""
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
            response = requests.post(GSHEETS_WEBAPP_URL, json=payload, timeout=10)
            if response.status_code == 200:
                success = True
        except Exception as e:
            pass
            
    # Always save a local copy as backup/fallback
    try:
        order_filename = os.path.join(ORDERS_DIR, f"order_{order_data['order_id']}.json")
        with open(order_filename, "w") as f:
            json.dump(order_data, f, indent=4)
        if not GSHEETS_WEBAPP_URL:
            success = True
    except Exception as e:
        pass
        
    return success

def update_order_status(order_id, status):
    """Update order status in Google Sheet Web App if configured, else local JSON."""
    success = False
    if GSHEETS_WEBAPP_URL:
        try:
            payload = {
                "action": "update_status",
                "order_id": order_id,
                "status": status
            }
            response = requests.post(GSHEETS_WEBAPP_URL, json=payload, timeout=10)
            if response.status_code == 200:
                success = True
        except Exception as e:
            pass
            
    # Update local file copy as well
    try:
        filename = f"order_{order_id}.json"
        file_path = os.path.join(ORDERS_DIR, filename)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                order_data = json.load(f)
            order_data["status"] = status
            with open(file_path, "w") as f:
                json.dump(order_data, f, indent=4)
            if not GSHEETS_WEBAPP_URL:
                success = True
    except Exception as e:
        pass
        
    return success

# Caching the data loading function
@st.cache_data
def load_data_from_excel(path_to_file):
    try:
        xl = pd.ExcelFile(path_to_file)
        data = {}
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            # Clean dataframe
            df = df.dropna(subset=['Product', 'Cost price'])
            df['Product'] = df['Product'].astype(str).str.strip()
            df['UOM'] = df['UOM'].astype(str).str.strip().fillna('')
            df['Cost price'] = pd.to_numeric(df['Cost price'], errors='coerce')
            df = df.dropna(subset=['Cost price'])
            # Sort products alphabetically
            df = df.sort_values(by='Product')
            data[sheet] = df
        return data, None
    except Exception as e:
        return None, str(e)

# Determine data source
excel_path = r"C:\Users\Chara RN\Downloads\Products available for staff to purchase.xlsx"
data = None
load_error = None

if os.path.exists(excel_path):
    data, load_error = load_data_from_excel(excel_path)
else:
    st.warning(f"Could not automatically find the Excel file at `{excel_path}`.")
    uploaded_file = st.file_uploader("Please upload the tuckshop products Excel workbook:", type=["xlsx"])
    if uploaded_file is not None:
        # Save temporary file to read
        temp_path = "temp_products.xlsx"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        data, load_error = load_data_from_excel(temp_path)

if load_error:
    st.error(f"Error loading Excel workbook: {load_error}")
    st.stop()

if data is None:
    st.info("Waiting for Excel workbook input...")
    st.stop()

# Initialize session state for quantities, checkout state, admin auth
if "quantities" not in st.session_state:
    st.session_state.quantities = {}

if "order_placed" not in st.session_state:
    st.session_state.order_placed = False

if "latest_order" not in st.session_state:
    st.session_state.latest_order = None

if "seller_authenticated" not in st.session_state:
    st.session_state.seller_authenticated = False

# Helper to clear cart
def clear_cart():
    st.session_state.quantities = {}
    st.session_state.order_placed = False
    st.session_state.latest_order = None

# Helper to logout seller
def logout_seller():
    st.session_state.seller_authenticated = False

# Helper to generate receipt HTML
def generate_receipt_html_helper(order, items_rows):
    receipt_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
            body {{
                font-family: 'Space Mono', monospace;
                color: #000;
                background-color: #fff;
                margin: 0;
                padding: 10px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .receipt-container {{
                width: 100%;
                max-width: 380px;
                border: 2px dashed #000;
                padding: 20px;
                box-sizing: border-box;
                background-color: #fff;
            }}
            .header {{
                text-align: center;
                margin-bottom: 20px;
            }}
            .title {{
                font-size: 1.6rem;
                font-weight: 700;
                margin: 0;
                letter-spacing: 1px;
            }}
            .subtitle {{
                font-size: 0.85rem;
                margin: 5px 0 0 0;
                font-weight: bold;
            }}
            .divider {{
                border-top: 1px dashed #000;
                margin: 15px 0;
            }}
            .info-section {{
                font-size: 0.85rem;
                line-height: 1.4;
                margin-bottom: 15px;
            }}
            .receipt-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.85rem;
            }}
            .receipt-table th {{
                border-bottom: 1px solid #000;
                padding: 5px 0;
                text-align: left;
            }}
            .receipt-table td {{
                padding: 6px 0;
            }}
            .total-row {{
                font-size: 1.2rem;
                font-weight: 700;
                display: flex;
                justify-content: space-between;
                margin-top: 10px;
            }}
            .footer {{
                text-align: center;
                margin-top: 25px;
                font-size: 0.8rem;
            }}
            .print-btn-container {{
                margin-bottom: 20px;
                text-align: center;
            }}
            .print-btn {{
                background-color: #2563eb;
                color: #fff;
                border: none;
                padding: 10px 24px;
                font-family: 'Space Mono', monospace;
                font-size: 1rem;
                font-weight: bold;
                border-radius: 6px;
                cursor: pointer;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                transition: background-color 0.2s;
            }}
            .print-btn:hover {{
                background-color: #1d4ed8;
            }}
            @media print {{
                .print-btn-container {{
                    display: none;
                }}
                .receipt-container {{
                    border: none;
                    padding: 0;
                    margin: 0;
                    max-width: 100%;
                }}
                body {{
                    padding: 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="print-btn-container">
            <button class="print-btn" onclick="window.print()">🖨️ PRINT / SAVE RECEIPT</button>
        </div>
        <div class="receipt-container">
            <div class="header">
                <div class="title">TUCKSHOP</div>
                <div class="subtitle">STAFF ORDER RECEIPT</div>
            </div>
            
            <div class="info-section">
                <strong>Order ID:</strong> {order["order_id"]}<br>
                <strong>Date:</strong> {order["date"]}<br>
                <strong>Staff Name:</strong> {order["staff_name"]}<br>
                <strong>Staff ID:</strong> {order["staff_id"]}
            </div>
            
            <div class="divider"></div>
            
            <table class="receipt-table">
                <thead>
                    <tr>
                        <th>ITEM</th>
                        <th style="text-align: center; width: 50px;">QTY</th>
                        <th style="text-align: right; width: 80px;">TOTAL</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                </tbody>
            </table>
            
            <div class="divider"></div>
            
            <div class="total-row">
                <span>TOTAL:</span>
                <span>${order["total"]:.2f}</span>
            </div>
            
            <div class="divider"></div>
            
            <div class="footer">
                Thank you for your order!<br>
                Please present this receipt at the tuckshop to collect your items.
            </div>
        </div>
    </body>
    </html>
    """
    return receipt_html

# Calculate Cart Items and Total
cart_items = []
cart_total = 0.0

for key, qty in list(st.session_state.quantities.items()):
    if qty > 0:
        parts = key.split("|||")
        if len(parts) == 4:
            category, name, uom, price_str = parts
            price = float(price_str)
            subtotal = price * qty
            cart_items.append({
                "key": key,
                "category": category,
                "name": name,
                "uom": uom,
                "price": price,
                "qty": qty,
                "subtotal": subtotal
            })
            cart_total += subtotal
        else:
            del st.session_state.quantities[key]

# ----------------- NAVIGATION & MODE SELECTOR -----------------
with st.sidebar:
    st.markdown("<div class='cart-header'>🧭 Navigation</div>", unsafe_allow_html=True)
    app_mode = st.selectbox("Select View Mode", ["🛒 Staff Storefront", "🔑 Seller Portal"], label_visibility="collapsed")
    db_status = "gspread" if GSHEETS_WEBAPP_URL else "local"
    if db_status == "gspread":
        st.markdown("<div style='text-align: center; color: #10b981; font-size: 0.85rem; font-weight: bold; margin-top: 10px;'>🟢 Cloud Connected</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='text-align: center; color: #f59e0b; font-size: 0.85rem; font-weight: bold; margin-top: 10px;'>🟡 Offline / Local Mode</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

# ----------------- RENDERING VIEWS -----------------

if app_mode == "🛒 Staff Storefront":
    # ----------------- SIDEBAR CART & CHECKOUT -----------------
    with st.sidebar:
        st.markdown("<div class='cart-header'>🛒 Your Cart</div>", unsafe_allow_html=True)
        
        if not cart_items:
            st.write("Your cart is empty. Add items from the catalog.")
        else:
            # Render cart items
            for item in cart_items:
                st.markdown(f"""
                <div class='cart-item'>
                    <div class='cart-item-title'>{item['name']}</div>
                    <div class='cart-item-details'>
                        <span>{item['qty']} x ${item['price']:.2f} ({item['uom']})</span>
                        <strong>${item['subtotal']:.2f}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class='cart-total'>
                <span>TOTAL DUE:</span>
                <span>${cart_total:.2f}</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.button("🧹 Clear Cart", on_click=clear_cart, use_container_width=True)
            
            st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
            st.markdown("<div class='cart-header'>📋 Checkout Details</div>", unsafe_allow_html=True)
            
            # Checkout Form
            staff_name = st.text_input("Full Name", placeholder="e.g. John Doe")
            staff_id = st.text_input("Staff ID / Department", placeholder="e.g. ENG-402")
            
            # Place Order button
            if st.button("🚀 Place Order & Get Receipt", type="primary", use_container_width=True):
                if not staff_name.strip():
                    st.error("Please enter your name.")
                elif not staff_id.strip():
                    st.error("Please enter your Staff ID or Department.")
                else:
                    # Place order
                    order_id = datetime.now().strftime("%Y%m%d%H%M%S")
                    order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    order_data = {
                        "order_id": order_id,
                        "date": order_date,
                        "staff_name": staff_name.strip(),
                        "staff_id": staff_id.strip(),
                        "status": "Pending",  # Default status for new orders
                        "items": [
                            {
                                "category": item["category"],
                                "name": item["name"],
                                "uom": item["uom"],
                                "price": item["price"],
                                "qty": item["qty"],
                                "subtotal": item["subtotal"]
                            }
                            for item in cart_items
                        ],
                        "total": cart_total
                    }
                    
                    # Save order (syncs to Google Sheets if configured, with local fallback)
                    save_order(order_data)
                    
                    st.session_state.latest_order = order_data
                    st.session_state.order_placed = True
                    st.success("Order processed successfully!")
                    st.rerun()

    # ----------------- STOREFRONT MAIN PANEL -----------------
    st.markdown("<h1 style='text-align: center; color: #1e3a8a; font-family: \"Outfit\", sans-serif;'>🎒 Tuckshop Staff Ordering Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 30px;'>Select items, enter checkout details in the sidebar, and print your order receipt.</p>", unsafe_allow_html=True)

    if st.session_state.order_placed and st.session_state.latest_order:
        # Display order receipt
        order = st.session_state.latest_order
        
        st.markdown("<div style='text-align: center; margin-bottom: 20px;'>", unsafe_allow_html=True)
        st.balloons()
        st.markdown("<h3>🎉 Order Successfully Placed!</h3>", unsafe_allow_html=True)
        st.markdown("Please print the receipt below and present it to the tuckshop to collect your order.", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        items_rows = ""
        for item in order["items"]:
            items_rows += f"""
            <tr>
                <td>{item['name']}<br><small>{item['uom']} @ ${item['price']:.2f}</small></td>
                <td style="text-align: center;">{item['qty']}</td>
                <td style="text-align: right;">${item['subtotal']:.2f}</td>
            </tr>
            """
        
        receipt_html = generate_receipt_html_helper(order, items_rows)
        components.html(receipt_html, height=550, scrolling=True)
        
        st.button("🔄 Back to Tuckshop / Order More", on_click=clear_cart)

    else:
        # ---------------- Search and Filtering ----------------
        search_query = st.text_input("🔍 Search tuckshop items...", "").strip().lower()

        if search_query:
            st.markdown(f"### Search Results for *\"{search_query}\"*")
            
            matches = []
            for category, df in data.items():
                for idx, row in df.iterrows():
                    product_name = str(row['Product'])
                    uom = str(row['UOM'])
                    if search_query in product_name.lower() or search_query in uom.lower():
                        matches.append((category, row))
            
            if not matches:
                st.info("No items found matching your search term. Try searching for something else.")
            else:
                num_cols = 3
                cols = st.columns(num_cols)
                for i, (category, row) in enumerate(matches):
                    col = cols[i % num_cols]
                    product_name = row['Product']
                    uom = row['UOM']
                    price = row['Cost price']
                    product_key = f"{category}|||{product_name}|||{uom}|||{price}"
                    current_qty = st.session_state.quantities.get(product_key, 0)
                    
                    with col:
                        with st.container(border=True):
                            st.markdown(f"<div class='product-title'>{product_name}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='product-meta'>Category: {category} | UOM: {uom}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='product-price'>${price:.2f}</div>", unsafe_allow_html=True)
                            
                            c1, c2, c3 = st.columns([1, 2, 1])
                            with c1:
                                if st.button("➖", key=f"dec_search_{product_key}_{i}"):
                                    if current_qty > 0:
                                        st.session_state.quantities[product_key] = current_qty - 1
                                        st.rerun()
                            with c2:
                                st.markdown(f"<div style='text-align: center; font-size: 1.2rem; font-weight: bold; margin-top: 5px;'>{current_qty}</div>", unsafe_allow_html=True)
                            with c3:
                                if st.button("➕", key=f"inc_search_{product_key}_{i}"):
                                    st.session_state.quantities[product_key] = current_qty + 1
                                    st.rerun()
                                    
        else:
            # ---------------- Tabbed Categories ----------------
            tab_titles = [f"📁 {sheet}" for sheet in data.keys()]
            tabs = st.tabs(tab_titles)
            
            for tab, (sheet, df) in zip(tabs, data.items()):
                with tab:
                    num_cols = 3
                    cols = st.columns(num_cols)
                    
                    for idx, row in df.reset_index(drop=True).iterrows():
                        col = cols[idx % num_cols]
                        product_name = row['Product']
                        uom = row['UOM']
                        price = row['Cost price']
                        product_key = f"{sheet}|||{product_name}|||{uom}|||{price}"
                        current_qty = st.session_state.quantities.get(product_key, 0)
                        
                        with col:
                            with st.container(border=True):
                                st.markdown(f"<div class='product-title'>{product_name}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='product-meta'>UOM: {uom}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='product-price'>${price:.2f}</div>", unsafe_allow_html=True)
                                
                                c1, c2, c3 = st.columns([1, 2, 1])
                                with c1:
                                    if st.button("➖", key=f"dec_{product_key}_{idx}"):
                                        if current_qty > 0:
                                            st.session_state.quantities[product_key] = current_qty - 1
                                            st.rerun()
                                with c2:
                                    st.markdown(f"<div style='text-align: center; font-size: 1.2rem; font-weight: bold; margin-top: 5px;'>{current_qty}</div>", unsafe_allow_html=True)
                                with c3:
                                    if st.button("➕", key=f"inc_{product_key}_{idx}"):
                                        st.session_state.quantities[product_key] = current_qty + 1
                                        st.rerun()

elif app_mode == "🔑 Seller Portal":
    # ----------------- SELLER PORTAL MAIN PANEL -----------------
    st.markdown("<h1 style='text-align: center; color: #1e3a8a; font-family: \"Outfit\", sans-serif;'>🔑 Tuckshop Seller Administration Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 30px;'>Log in to review receipts, track daily stats, and mark orders as completed.</p>", unsafe_allow_html=True)

    if not st.session_state.seller_authenticated:
        # Password authentication
        col_auth_left, col_auth_center, col_auth_right = st.columns([1, 2, 1])
        with col_auth_center:
            with st.container(border=True):
                st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Seller Sign In</h3>", unsafe_allow_html=True)
                password = st.text_input("Enter Seller Password", type="password")
                if st.button("Unlock Admin Panel", type="primary", use_container_width=True):
                    if password == "sales123":
                        st.session_state.seller_authenticated = True
                        st.success("Access Granted!")
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please try again.")
    else:
        # 1. Load Orders
        orders, db_source = load_orders()

        # Seller sidebar
        with st.sidebar:
            st.markdown("<div class='cart-header'>🔑 Admin Session</div>", unsafe_allow_html=True)
            if db_source == "gspread":
                st.markdown("<div style='color: #10b981; font-size: 0.9rem; font-weight: bold; margin-bottom: 15px;'>🟢 Cloud Sync Active</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color: #f59e0b; font-size: 0.9rem; font-weight: bold; margin-bottom: 15px;'>🟡 Local Fallback Mode</div>", unsafe_allow_html=True)
            st.button("🔄 Refresh Orders", use_container_width=True)
            st.button("🔒 Lock Portal / Log Out", on_click=logout_seller, use_container_width=True)

        # 2. Analytics metrics
        total_orders = len(orders)
        total_revenue = sum(o.get("total", 0.0) for o in orders)
        pending_orders = sum(1 for o in orders if o.get("status") == "Pending")
        completed_orders = sum(1 for o in orders if o.get("status") == "Completed")

        # Stats Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value'>{total_orders}</div>
                <div class='stat-label'>Total Orders</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value'>${total_revenue:.2f}</div>
                <div class='stat-label'>Total Revenue</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value' style='color: #d97706;'>{pending_orders}</div>
                <div class='stat-label'>Pending</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-value' style='color: #059669;'>{completed_orders}</div>
                <div class='stat-label'>Completed</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)

        # 3. Filtering options
        filter_status = st.radio(
            "Filter Orders by Status:",
            ["All", "Pending", "Completed"],
            horizontal=True
        )

        filtered_orders = [o for o in orders if filter_status == "All" or o.get("status") == filter_status]

        st.markdown(f"### Receipts list ({len(filtered_orders)} orders)")

        # 4. Display receipts list
        if not filtered_orders:
            st.info("No orders found matching the selected filter.")
        else:
            for idx, order in enumerate(filtered_orders):
                badge_class = "badge-pending" if order["status"] == "Pending" else "badge-completed"
                
                with st.container(border=True):
                    col_info, col_toggle = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"""
                        <div style='display: flex; align-items: center; gap: 15px; margin-bottom: 6px;'>
                            <span style='font-size: 1.15rem; font-weight: 700; color: #1e293b;'>Order #{order['order_id']}</span>
                            <span class='badge {badge_class}'>{order['status']}</span>
                        </div>
                        <div style='font-size: 0.95rem; color: #475569;'>
                            <strong>Staff:</strong> {order['staff_name']} ({order['staff_id']}) &nbsp;|&nbsp;
                            <strong>Date:</strong> {order['date']} &nbsp;|&nbsp;
                            <strong>Total:</strong> <strong style='color: #10b981;'>${order['total']:.2f}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_toggle:
                        # Status toggle button
                        if order["status"] == "Pending":
                            if st.button("Mark Completed ✅", key=f"complete_{order['order_id']}_{idx}", use_container_width=True):
                                if update_order_status(order["order_id"], "Completed"):
                                    st.success(f"Order #{order['order_id']} marked as completed!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update status on Cloud. Please try again.")
                        else:
                            if st.button("Mark Pending ⏳", key=f"pending_{order['order_id']}_{idx}", use_container_width=True):
                                if update_order_status(order["order_id"], "Pending"):
                                    st.success(f"Order #{order['order_id']} marked as pending.")
                                    st.rerun()
                                else:
                                    st.error("Failed to update status on Cloud. Please try again.")
                    
                    # Expander for receipt details
                    with st.expander("🔍 View Items / Print Receipt"):
                        # Render markdown table of items
                        table_md = "| Product | Category | UOM | Qty | Cost | Subtotal |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"
                        for item in order["items"]:
                            table_md += f"| {item['name']} | {item['category']} | {item['uom']} | {item['qty']} | ${item['price']:.2f} | ${item['subtotal']:.2f} |\n"
                        st.markdown(table_md)
                        
                        # Printable Receipt iframe Toggle
                        show_print = st.toggle("Show printable receipt format", key=f"print_toggle_{order['order_id']}_{idx}")
                        if show_print:
                            items_rows = ""
                            for item in order["items"]:
                                items_rows += f"""
                                <tr>
                                    <td>{item['name']}<br><small>{item['uom']} @ ${item['price']:.2f}</small></td>
                                    <td style="text-align: center;">{item['qty']}</td>
                                    <td style="text-align: right;">${item['subtotal']:.2f}</td>
                                </tr>
                                """
                            receipt_html = generate_receipt_html_helper(order, items_rows)
                            components.html(receipt_html, height=450, scrolling=True)
