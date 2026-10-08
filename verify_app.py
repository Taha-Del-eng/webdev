import os
import re

DB_PATH="verify_yours_mart.db"
os.environ["DATABASE_URL"]=f"sqlite:///{DB_PATH}"
os.environ["SECRET_KEY"]="verify-secret"
from app import app

app.config.update(TESTING=True)
client=app.test_client()

for path in ["/","/shop","/health","/login","/signup","/admin-login"]:
    r=client.get(path)
    assert r.status_code < 500, (path,r.status_code)

assert client.get("/health").json["status"]=="ok"
assert client.get("/product/aero-oversized-tee").status_code==200

# CSRF is required for every state-changing request.
assert client.post("/logout").status_code in (302, 401)
assert client.get("/logout").status_code == 405

def csrf():
    r=client.get("/signup")
    match=re.search(r'name="csrf-token" content="([^"]+)"',r.get_data(as_text=True))
    if not match:
        match=re.search(r'name="_csrf" value="([^"]+)"',r.get_data(as_text=True))
    assert match, "CSRF token not found"
    return match.group(1)

token=csrf()

# Server-side signup validation.
bad=client.post("/signup",data={
    "_csrf":token,"full_name":"","email":"not-an-email","username":"x","password":"short"
})
assert bad.status_code==200
assert "valid full name" in bad.get_data(as_text=True)

token=csrf()
signup=client.post("/signup",data={
    "_csrf":token,"full_name":"Verify User","email":"verify@example.com",
    "username":"verify_user","password":"strong-password-123"
})
assert signup.status_code==302

# Product detail recommendations must render successfully.
assert client.get("/product/aero-oversized-tee").status_code==200

# Add a valid cart line, then complete a COD checkout.
token=csrf()
add=client.post("/cart/add/1",data={
    "_csrf":token,"quantity":"2","size":"M","color":"Black"
})
assert add.status_code==302

checkout=client.get("/checkout")
assert checkout.status_code==200
token=csrf()
placed=client.post("/checkout",data={
    "_csrf":token,"full_name":"Verify User","phone":"03001234567",
    "address":"1 Verification Street","city":"Karachi","postal_code":"74000",
    "instructions":"","payment_method":"COD"
})
assert placed.status_code==200
assert "placed successfully" in placed.get_data(as_text=True)

# Stock must have been reserved atomically.
with client.application.app_context():
    from app.main import one
    product=one("SELECT stock FROM products WHERE id=1")
    order=one("SELECT COUNT(*) n FROM orders WHERE user_id=:u",{"u":1})
    assert product["stock"]==36
    assert int(order["n"])==1

print("Yours Mart smoke verification passed.")

try:
    os.remove(DB_PATH)
except FileNotFoundError:
    pass
