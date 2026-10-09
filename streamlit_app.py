import streamlit as st
import sqlite3
import uuid
import pandas as pd
from datetime import datetime
from pathlib import Path

DB = Path(__file__).parent / "campusbites.db"
MENU = {"Idli (2 pcs)": 25, "Plain Dosa": 35, "Masala Dosa": 50, "Veg Fried Rice": 60,
        "Veg Meals": 75, "Samosa": 15, "Tea": 10, "Coffee": 15}

st.set_page_config(page_title="CampusBites | RVR & JC", page_icon="🍱", layout="wide")

def db():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def setup():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, token INTEGER,
            name TEXT, items TEXT, total REAL, payment TEXT, status TEXT, created TEXT)""")
        con.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
        con.execute("INSERT OR IGNORE INTO settings VALUES('token','101')")

def all_orders():
    with db() as con:
        return pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", con)

def submit_order(name, selected, total):
    with db() as con:
        token = int(con.execute("SELECT value FROM settings WHERE key='token'").fetchone()["value"])
        con.execute("UPDATE settings SET value=? WHERE key='token'", (str(token + 1),))
        code = uuid.uuid4().hex[:8].upper()
        items = ", ".join(f"{k} x{v}" for k, v in selected.items())
        con.execute("INSERT INTO orders(code,token,name,items,total,payment,status,created) VALUES(?,?,?,?,?,?,?,?)",
                    (code, token, name, items, total, "Demo only — not verified", "Preparing",
                     datetime.now().strftime("%d %b %Y, %I:%M %p")))
    return code, token

setup()
st.markdown("""
<style>
.block-container{padding-top:1.5rem}
.hero{background:linear-gradient(120deg,#173d31,#2c8061);padding:1.5rem;border-radius:18px;color:white;margin-bottom:1rem}
.hero h1{color:white;margin:0}.hero p{color:#e5f5ec;margin:.35rem 0 0}
</style>
<div class="hero"><h1>🍱 CampusBites</h1><p>Smart canteen pre-ordering · Skip the queue · Pick up by token</p></div>
""", unsafe_allow_html=True)

student, kitchen, admin = st.tabs(["🛍️ Student ordering", "👨‍🍳 Kitchen counter", "📊 Admin dashboard"])

with student:
    menu_col, info_col = st.columns([1.4, 1])
    with menu_col:
        st.subheader("Today's menu")
        st.caption("Sample prices — adjust them to match your college canteen.")
        with st.form("order"):
            name = st.text_input("Your name", placeholder="Enter your name")
            quantities = {}
            cols = st.columns(2)
            for i, (item, price) in enumerate(MENU.items()):
                with cols[i % 2]:
                    quantities[item] = st.number_input(f"{item} · ₹{price}", 0, 20, 0, key="q_"+item)
            total = sum(MENU[k] * int(v) for k, v in quantities.items())
            st.markdown(f"### Total: ₹{total}")
            clicked = st.form_submit_button("Place demo order", type="primary", use_container_width=True)
        if clicked:
            selected = {k: int(v) for k, v in quantities.items() if v > 0}
            if not name.strip():
                st.error("Please enter your name.")
            elif not selected:
                st.error("Choose at least one menu item.")
            else:
                code, token = submit_order(name.strip(), selected, total)
                st.session_state["last_order"] = {"code": code, "token": token, "name": name.strip(),
                                                   "items": selected, "total": total}
                st.success("Order placed!")
    with info_col:
        st.subheader("Pickup steps")
        st.markdown("1. Choose food and quantities.\n2. Place your order.\n3. Note your token.\n4. Pick up when the kitchen marks it **Ready**.")
        st.info("Prototype only: no real UPI/card payment is collected or verified.")
        last = st.session_state.get("last_order")
        if last:
            st.divider()
            st.success("Your latest order")
            st.metric("Pickup token", f"#{last['token']}")
            st.write("**Order ID:**", f"`{last['code']}`")
            st.write("**Name:**", last["name"])
            st.write("**Items:**", ", ".join(f"{k} × {v}" for k, v in last["items"].items()))
            st.write(f"**Total: ₹{last['total']}**")

with kitchen:
    st.subheader("Kitchen order queue")
    st.caption("Move orders through Preparing → Ready → Completed.")
    orders = all_orders()
    if orders.empty:
        st.info("No orders yet. Place a test order in Student ordering.")
    else:
        active = orders[orders.status != "Completed"].sort_values("id")
        if active.empty:
            st.info("All orders are completed.")
        for _, order in active.iterrows():
            with st.container(border=True):
                a, b, c = st.columns([1.2, 2.5, 1.4])
                a.markdown(f"### Token #{int(order['token'])}")
                a.write(order["name"])
                b.write(order["items"])
                b.write(f"₹{order['total']:.0f} · {order['created']}")
                c.write(f"**{order['status']}**")
                if order["status"] == "Preparing":
                    if c.button("Mark Ready", key=f"ready{order['id']}", use_container_width=True):
                        with db() as con:
                            con.execute("UPDATE orders SET status='Ready' WHERE id=?", (int(order["id"]),))
                        st.rerun()
                elif order["status"] == "Ready":
                    if c.button("Mark Completed", key=f"done{order['id']}", use_container_width=True):
                        with db() as con:
                            con.execute("UPDATE orders SET status='Completed' WHERE id=?", (int(order["id"]),))
                        st.rerun()
        if st.button("Refresh queue"):
            st.rerun()

with admin:
    st.subheader("Canteen overview")
    orders = all_orders()
    if orders.empty:
        st.info("No orders recorded yet.")
        st.metric("Total orders", 0)
        st.metric("Demo order value", "₹0")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Total orders", len(orders))
        b.metric("Demo order value", f"₹{orders.total.sum():.0f}")
        c.metric("Preparing", int((orders.status == "Preparing").sum()))
        d.metric("Ready for pickup", int((orders.status == "Ready").sum()))
        st.write("Completed orders:", int((orders.status == "Completed").sum()))
        st.divider()
        st.subheader("Order history")
        st.dataframe(orders[["code","token","name","items","total","payment","status","created"]],
                     use_container_width=True, hide_index=True)
        st.download_button("Download order history (CSV)", orders.to_csv(index=False).encode("utf-8"),
                           "campusbites_orders.csv", "text/csv")
        st.warning("For real use, add verified payments, login/access control, backups, and a shared managed database. Local SQLite is suitable only for this demo.")
        with st.expander("Reset demo data"):
            st.caption("This deletes all saved orders.")
            if st.button("Delete all demo orders"):
                with db() as con:
                    con.execute("DELETE FROM orders")
                    con.execute("UPDATE settings SET value='101' WHERE key='token'")
                st.rerun()

st.divider()
st.caption("CampusBites · College canteen prototype · Payment is simulated and not verified.")
