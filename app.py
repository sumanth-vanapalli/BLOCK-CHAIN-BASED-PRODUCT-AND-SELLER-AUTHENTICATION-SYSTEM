from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from web3 import Web3
import json
import qrcode
import os
import mysql.connector
from config import (
    GANACHE_URL,
    CONTRACT_ADDRESS,
    DB_HOST,
    DB_USER,
    DB_PASSWORD,
    DB_NAME
)

app = Flask(__name__)
app.secret_key = "secret123"

# --------------------------------------------------
# BLOCKCHAIN CONNECTION
# --------------------------------------------------
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))
if web3.is_connected():
    print("✅ Connected to Ganache")

with open("blockchain/contract_abi.json", "r") as f:
    abi = json.load(f)

contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)
web3.eth.default_account = web3.eth.accounts[0]

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# --------------------------------------------------
# SECURITY DECORATORS
# --------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session or session["user"]["role"] != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap

# --------------------------------------------------
# LANDING PAGE
# --------------------------------------------------
@app.route("/")
def landing():
    return render_template("landing.html")

# --------------------------------------------------
# REGISTER
# --------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
                (username, password, role)
            )
            db.commit()
        except:
            return "❌ Username already exists"

        return redirect(url_for("login"))
    return render_template("register.html")

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (request.form["username"],)
        )
        user = cursor.fetchone()

        if user and user["is_active"] and check_password_hash(user["password"], request.form["password"]):
            session["user"] = user

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        elif user and not user["is_active"]:
            return "❌ Account disabled by Admin"

        return "❌ Invalid login"

    return render_template("login.html")

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

# --------------------------------------------------
# USER DASHBOARD
# --------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    products = []

    if session["user"]["role"] == "manufacturer":
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM products WHERE added_by=%s",
            (session["user"]["id"],)
        )
        products = cursor.fetchall()

    return render_template("dashboard.html", products=products)

# --------------------------------------------------
# ADD PRODUCT (MANUFACTURER)
# --------------------------------------------------
@app.route("/add_product", methods=["GET", "POST"])
@login_required
def add_product():
    if session["user"]["role"] != "manufacturer":
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        tx = contract.functions.addProduct(
            request.form["name"],
            request.form["manufacturer"],
            request.form["product_id"]
        ).transact()

        tx_hash = web3.to_hex(tx)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO products (product_id, name, manufacturer, tx_hash, added_by)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            request.form["product_id"],
            request.form["name"],
            request.form["manufacturer"],
            tx_hash,
            session["user"]["id"]
        ))
        db.commit()

        qr = qrcode.make(request.form["product_id"])
        os.makedirs("static/qr_codes", exist_ok=True)
        qr.save(f"static/qr_codes/{request.form['product_id']}.png")

        return redirect(url_for("dashboard"))

    return render_template("add_product.html")

# --------------------------------------------------
# VERIFY PRODUCT
# --------------------------------------------------
@app.route("/verify_product", methods=["GET", "POST"])
def verify_product():
    if request.method == "POST":
        name, manufacturer, status = contract.functions.verifyProduct(
            request.form["product_id"]
        ).call()

        return render_template(
            "result.html",
            name=name,
            manufacturer=manufacturer,
            status=status
        )

    return render_template("verify_product.html")

# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id, username, role, is_active FROM users")
    users = cursor.fetchall()

    cursor.execute("""
        SELECT p.product_id, p.name, p.manufacturer, p.tx_hash, u.username
        FROM products p
        JOIN users u ON p.added_by = u.id
    """)
    products = cursor.fetchall()

    return render_template("admin_dashboard.html", users=users, products=products)

# --------------------------------------------------
# ADMIN ENABLE/DISABLE USER
# --------------------------------------------------
@app.route("/admin/toggle_user/<int:user_id>")
@admin_required
def toggle_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE users SET is_active = NOT is_active WHERE id=%s",
        (user_id,)
    )
    db.commit()
    return redirect(url_for("admin_dashboard"))

# --------------------------------------------------
# RUN APP
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
