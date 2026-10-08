import os
import re
from werkzeug.security import generate_password_hash

DB_PATH="verify_yours_mart.db"
os.environ["DATABASE_URL"]=f"sqlite:///{DB_PATH}"
os.environ["SECRET_KEY"]="verify-secret"
os.environ["ADMIN_USERNAME"]="verify_admin"
os.environ["ADMIN_EMAIL"]="admin@example.com"
os.environ["ADMIN_NAME"]="Verify Admin"
os.environ["ADMIN_PASSWORD_HASH"]=generate_password_hash("AdminPass123!")
os.environ["SUPERADMIN_USERNAME"]="verify_super"
os.environ["SUPERADMIN_EMAIL"]="super@example.com"
os.environ["SUPERADMIN_NAME"]="Verify Superadmin"
os.environ["SUPERADMIN_PASSWORD_HASH"]=generate_password_hash("SuperPass123!")

from app import app
app.config.update(TESTING=True)
client=app.test_client()

for path in ["/","/shop","/health","/login","/signup","/admin-login","/superadmin","/admin"]:
    r=client.get(path)
    assert r.status_code < 500, (path,r.status_code)

assert client.get("/health").json["status"]=="ok"
assert client.get("/product/aero-oversized-tee").status_code==200
assert client.get("/product/not-a-real-product").status_code==404

def csrf():
    r=client.get("/signup")
    match=re.search(r'name="csrf-token" content="([^"]+)"',r.get_data(as_text=True))
    assert match, "CSRF token not found"
    return match.group(1)

# CSRF protection.
assert client.post("/logout").status_code == 400
token=csrf()

# Customer signup.
bad=client.post("/signup",data={"_csrf":token,"full_name":"","email":"bad","username":"x","password":"short"})
assert bad.status_code==200
token=csrf()
signup=client.post("/signup",data={"_csrf":token,"full_name":"Verify User","email":"verify@example.com","username":"verify_user","password":"strong-password-123"})
assert signup.status_code==302

# Cart and checkout with COD.
token=csrf()
add=client.post("/cart/add/1",data={"_csrf":token,"quantity":"2","size":"M","color":"Black"})
assert add.status_code==302
checkout=client.get("/checkout")
assert checkout.status_code==200
token=csrf()
placed=client.post("/checkout",data={"_csrf":token,"full_name":"Verify User","phone":"03001234567","province":"Sindh","area":"Gulshan","address":"1 Verification Street","city":"Karachi","postal_code":"74000","instructions":"","payment_method":"cod"})
assert placed.status_code==302
order_page=client.get(placed.location)
assert order_page.status_code==200
assert "YM-" in order_page.get_data(as_text=True)

with app.app_context():
    from app.main import one
    product=one("SELECT stock FROM products WHERE id=1")
    order=one("SELECT COUNT(*) n FROM orders WHERE user_id=:u",{"u":1})
    payment=one("SELECT method,status FROM payments ORDER BY id DESC LIMIT 1")
    assert product["stock"]==36
    assert int(order["n"])==1
    assert payment["method"]=="COD"

# Customer cannot access admin or superadmin.
client.get("/logout") if False else None
# session remains customer here; protected admin routes must redirect/deny.
assert client.get("/admin").status_code in (302,403)
assert client.get("/superadmin").status_code in (302,403)

# Admin login and dashboard.
client = app.test_client()
token=re.search(r'name="csrf-token" content="([^"]+)"',client.get("/admin-login").get_data(as_text=True)).group(1)
admin_login=client.post("/admin-login",data={"_csrf":token,"username":"verify_admin","password":"AdminPass123!"})
assert admin_login.status_code==302
assert client.get("/admin").status_code==200
assert client.get("/superadmin").status_code in (302,403)

# Superadmin login is separate and can manage admin accounts.
client = app.test_client()
token=re.search(r'name="csrf-token" content="([^"]+)"',client.get("/admin-login").get_data(as_text=True)).group(1)
super_login=client.post("/admin-login",data={"_csrf":token,"username":"verify_super","password":"SuperPass123!"})
assert super_login.status_code==302
assert client.get("/superadmin").status_code==200

print("Yours Mart production smoke verification passed.")
try:
    os.remove(DB_PATH)
except FileNotFoundError:
    pass
