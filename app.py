import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = "navymart-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
ADMIN_USERNAME = "mtaha0510"
ADMIN_PASSWORD = "admin123"

DEFAULT_PRODUCTS = [
    ("Wireless Earbuds Pro", "Electronics", 4999, 35),
    ("Smart Watch Series 5", "Electronics", 8999, 12),
    ("Bluetooth Speaker", "Electronics", 3499, 4),
    ("Gaming Mouse RGB", "Electronics", 2799, 50),
    ("Men Running Shoes", "Fashion", 5499, 22),
    ("Leather Wallet", "Fashion", 1299, 60),
    ("Women Handbag", "Fashion", 3999, 3),
    ("Sunglasses UV400", "Fashion", 999, 40),
    ("Non-Stick Fry Pan", "Home", 1899, 18),
    ("Table Lamp LED", "Home", 1499, 27),
    ("Cotton Bedsheet Set", "Home", 2999, 9),
    ("Water Bottle 1L", "Home", 599, 100),
]

PRODUCT_IMAGE_URLS = {
    "Wireless Earbuds Pro": "https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?auto=format&fit=crop&w=900&q=80",
    "Smart Watch Series 5": "https://images.unsplash.com/photo-1546868871-7041f2a55e12?auto=format&fit=crop&w=900&q=80",
    "Bluetooth Speaker": "https://images.unsplash.com/photo-1511379938547-c1f69419868d?auto=format&fit=crop&w=900&q=80",
    "Gaming Mouse RGB": "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=900&q=80",
    "Men Running Shoes": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",
    "Leather Wallet": "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=80",
    "Women Handbag": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80",
    "Sunglasses UV400": "https://images.unsplash.com/photo-1577803947579-9f7ddd8a8445?auto=format&fit=crop&w=900&q=80",
    "Non-Stick Fry Pan": "https://images.unsplash.com/photo-1582515073490-39981397c445?auto=format&fit=crop&w=900&q=80",
    "Table Lamp LED": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
    "Cotton Bedsheet Set": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80",
    "Water Bottle 1L": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=80",
}


def get_product_image_url(name):
    if not name:
        return PRODUCT_IMAGE_URLS.get("Water Bottle 1L")
    clean_name = name.strip()
    return PRODUCT_IMAGE_URLS.get(clean_name, PRODUCT_IMAGE_URLS.get("Water Bottle 1L"))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA busy_timeout = 30000")
    except sqlite3.OperationalError:
        pass
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
        """
    )

    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
            DEFAULT_PRODUCTS,
        )

    conn.commit()
    conn.close()


init_db()


def register_user(full_name, email, username, password):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (full_name, email, username, password) VALUES (?, ?, ?, ?)",
            (full_name.strip(), email.strip(), username.strip(), password.strip()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def find_user_by_username(username):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_products(q="", cat="", sort=""):
    conn = get_db_connection()
    query = "SELECT * FROM products WHERE name LIKE ?"
    params = [f"%{q}%"]
    if cat:
        query += " AND category = ?"
        params.append(cat)

    order = {"low": " ORDER BY price ASC", "high": " ORDER BY price DESC"}.get(sort, " ORDER BY id DESC")
    query += order
    rows = conn.execute(query, params).fetchall()
    conn.close()
    products = [dict(row) for row in rows]
    for product in products:
        product["image_url"] = get_product_image_url(product.get("name", ""))
    return products


def get_categories():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    conn.close()
    return [row["category"] for row in rows]


def get_cart():
    cart = session.get("cart", {})
    cleaned = {}
    for key, value in cart.items():
        try:
            product_id = int(key)
            quantity = int(value)
            if product_id > 0 and quantity > 0:
                cleaned[product_id] = quantity
        except (TypeError, ValueError):
            continue
    session["cart"] = cleaned
    return cleaned


def get_cart_products():
    cart = get_cart()
    if not cart:
        return [], 0

    ids = list(cart.keys())
    placeholders = ", ".join("?" for _ in ids)
    conn = get_db_connection()
    rows = conn.execute(f"SELECT * FROM products WHERE id IN ({placeholders})", ids).fetchall()
    conn.close()

    items = []
    total = 0
    for row in rows:
        product = dict(row)
        qty = cart.get(product["id"], 0)
        subtotal = product["price"] * qty
        total += subtotal
        items.append({
            "id": product["id"],
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "qty": qty,
            "subtotal": subtotal,
        })
    return items, total


def add_product(name, category, price, stock):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        (name.strip(), category.strip(), float(price), int(stock)),
    )
    conn.commit()
    conn.close()


def get_product_by_id(product_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    product = dict(row)
    product["image_url"] = get_product_image_url(product.get("name", ""))
    return product


def update_product(product_id, name, category, price, stock):
    conn = get_db_connection()
    conn.execute(
        "UPDATE products SET name = ?, category = ?, price = ?, stock = ? WHERE id = ?",
        (name.strip(), category.strip(), float(price), int(stock), product_id),
    )
    conn.commit()
    conn.close()


def rename_category(old_category, new_category):
    conn = get_db_connection()
    conn.execute(
        "UPDATE products SET category = ? WHERE category = ?",
        (new_category.strip(), old_category.strip()),
    )
    conn.commit()
    conn.close()


@app.route("/")
def landing_page():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    error = None
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not full_name or not email or not username or not password:
            error = "Please fill in all fields."
        elif register_user(full_name, email, username, password):
            session["user"] = username
            return redirect(url_for("shop_page"))
        else:
            error = "Username or email already exists."

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = find_user_by_username(username)

        if user and user["password"] == password:
            session["user"] = user["username"]
            return redirect(url_for("shop_page"))
        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login_page():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid admin username or password."
    return render_template("admin_login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("admin", None)
    session.pop("cart", None)
    return redirect(url_for("landing_page"))


@app.route("/shop")
def shop_page():
    if "user" not in session:
        return redirect(url_for("login_page"))

    q = request.args.get("q", "")
    cat = request.args.get("cat", "")
    sort = request.args.get("sort", "")
    products = get_products(q=q, cat=cat, sort=sort)
    categories = get_categories()
    cart_count = sum(get_cart().values())
    return render_template("user.html", products=products, categories=categories, q=q, cat=cat, sort=sort, username=session["user"], cart_count=cart_count)


@app.route("/profile", methods=["GET", "POST"])
def profile_page():
    if "user" not in session:
        return redirect(url_for("login_page"))

    current_user = find_user_by_username(session["user"])
    if not current_user:
        session.pop("user", None)
        return redirect(url_for("login_page"))

    error = None
    success = None
    if request.method == "POST":
        new_full_name = request.form.get("full_name", "").strip()
        new_email = request.form.get("email", "").strip()
        new_username = request.form.get("username", "").strip()
        new_password = request.form.get("password", "").strip()

        if not new_full_name or not new_email or not new_username or not new_password:
            error = "Full name, email, username, and password are required."
        else:
            conn = get_db_connection()
            duplicate_username = conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (new_username, current_user["id"]),
            ).fetchone()
            duplicate_email = conn.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (new_email, current_user["id"]),
            ).fetchone()
            if duplicate_username:
                error = "This username is already in use."
            elif duplicate_email:
                error = "This email is already registered."
            else:
                conn.execute(
                    "UPDATE users SET full_name = ?, email = ?, username = ?, password = ? WHERE id = ?",
                    (new_full_name, new_email, new_username, new_password, current_user["id"]),
                )
                conn.commit()
                conn.close()
                session["user"] = new_username
                current_user = {
                    "id": current_user["id"],
                    "full_name": new_full_name,
                    "email": new_email,
                    "username": new_username,
                    "password": new_password,
                }
                success = "Profile updated successfully."
                return render_template("profile.html", user=current_user, success=success, error=None)
            conn.close()

    return render_template("profile.html", user=current_user, success=success, error=error)


@app.route("/cart")
def cart_page():
    if "user" not in session:
        return redirect(url_for("login_page"))

    items, total = get_cart_products()
    return render_template("cart.html", items=items, total=total, cart_count=sum(get_cart().values()))


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if "user" not in session:
        return redirect(url_for("login_page"))

    product = get_product_by_id(product_id)
    if not product:
        return redirect(url_for("shop_page"))

    cart = get_cart()
    current_qty = cart.get(product_id, 0)
    if current_qty < product["stock"]:
        cart[product_id] = current_qty + 1
        session["cart"] = cart

    return redirect(request.referrer or url_for("shop_page"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    if "user" not in session:
        return redirect(url_for("login_page"))

    cart = get_cart()
    cart.pop(product_id, None)
    session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    if "user" not in session:
        return redirect(url_for("login_page"))

    product = get_product_by_id(product_id)
    if not product:
        return redirect(url_for("cart_page"))

    qty = int(request.form.get("quantity", 1))
    cart = get_cart()
    if qty <= 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = max(1, min(product["stock"], qty))
    session["cart"] = cart
    return redirect(url_for("cart_page"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout_page():
    if "user" not in session:
        return redirect(url_for("login_page"))

    items, total = get_cart_products()
    if not items:
        return redirect(url_for("shop_page"))

    payment_methods = ["Cash on Delivery", "Credit Card", "Debit Card", "Bank Transfer"]
    selected_method = request.form.get("payment_method", payment_methods[0])
    error = None
    success = None

    if request.method == "POST":
        if selected_method in ["Credit Card", "Debit Card"]:
            card_name = request.form.get("card_name", "").strip()
            card_number = request.form.get("card_number", "").strip()
            expiry = request.form.get("expiry", "").strip()
            cvv = request.form.get("cvv", "").strip()
            if not (card_name and card_number and expiry and cvv):
                error = "Please complete the card details for the selected payment method."
                return render_template("checkout.html", items=items, total=total, payment_methods=payment_methods, selected_method=selected_method, error=error)

        session["cart"] = {}
        success = f"Order placed successfully with {selected_method}."
        return render_template("checkout.html", items=[], total=0, payment_methods=payment_methods, selected_method=selected_method, success=success)

    return render_template("checkout.html", items=items, total=total, payment_methods=payment_methods, selected_method=selected_method, error=error, success=success)


@app.route("/admin")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login_page"))

    products = get_products()
    categories = get_categories()
    return render_template("admin.html", products=products, categories=categories)


@app.route("/admin/add", methods=["POST"])
def admin_add_product():
    if "admin" not in session:
        return redirect(url_for("admin_login_page"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "0").strip()
    stock = request.form.get("stock", "0").strip()
    if name and category and price and stock:
        add_product(name, category, price, stock)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/update/<int:product_id>", methods=["POST"])
def admin_update_product(product_id):
    if "admin" not in session:
        return redirect(url_for("admin_login_page"))

    product = get_product_by_id(product_id)
    if not product:
        return redirect(url_for("admin_dashboard"))

    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "0").strip()
    stock = request.form.get("stock", "0").strip()
    if name and category and price and stock:
        update_product(product_id, name, category, price, stock)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/update-category", methods=["POST"])
def admin_update_category():
    if "admin" not in session:
        return redirect(url_for("admin_login_page"))

    old_category = request.form.get("old_category", "").strip()
    new_category = request.form.get("new_category", "").strip()
    if old_category and new_category:
        rename_category(old_category, new_category)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    if "admin" not in session:
        return redirect(url_for("admin_login_page"))

    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/add", methods=["POST"])  # backward compatibility for older form action
def legacy_add_product():
    if "admin" in session:
        return admin_add_product()
    return redirect(url_for("login_page"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
