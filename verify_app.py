import os
import re
import tempfile
from pathlib import Path
from io import BytesIO
from PIL import Image
from werkzeug.security import generate_password_hash
from sqlalchemy import text

_VERIFY_TEMP = tempfile.TemporaryDirectory(prefix="yours-mart-verify-")
DB_PATH = Path(_VERIFY_TEMP.name) / "verify_yours_mart.db"

os.environ["DATABASE_URL"]=f"sqlite:///{DB_PATH.resolve()}"
os.environ["SECRET_KEY"]="verify-secret"
os.environ["ADMIN_USERNAME"]="verify_admin"
os.environ["ADMIN_EMAIL"]="admin@example.com"
os.environ["ADMIN_NAME"]="Verify Admin"
os.environ["ADMIN_PASSWORD_HASH"]=generate_password_hash("AdminPass123!")
os.environ["SUPERADMIN_USERNAME"]="verify_super"
os.environ["SUPERADMIN_EMAIL"]="super@example.com"
os.environ["SUPERADMIN_NAME"]="Verify Superadmin"
os.environ["SUPERADMIN_PASSWORD_HASH"]=generate_password_hash("SuperPass123!")
os.environ.pop("AI_API_KEY",None)
os.environ.pop("AI_ASSISTANT_API_KEY",None)

from app import app
from app.main import one, engine
app.config.update(TESTING=True)

client=app.test_client()

# Public pages and health.
for path in ["/","/shop","/health","/login","/signup","/admin-login","/admin","/superadmin"]:
    r=client.get(path)
    assert r.status_code < 500, (path,r.status_code)
assert client.get("/health").json["status"]=="ok"
assert client.get("/product/aero-oversized-tee").status_code==200
assert client.get("/product/not-a-real-product").status_code==404

def csrf(path="/signup", test_client=None):
    c=test_client or client
    r=c.get(path)
    match=re.search(r'name="csrf-token" content="([^"]+)"',r.get_data(as_text=True))
    assert match, f"CSRF token not found on {path}"
    return match.group(1)

# State-changing requests require CSRF.
assert client.post("/logout").status_code == 400
token=csrf()
assert client.post("/signup",data={"_csrf":token,"full_name":"","email":"bad","username":"x","password":"short"}).status_code==200

# Deterministic customer signup.
token=csrf()
signup=client.post("/signup",data={"_csrf":token,"full_name":"Verify User","email":"verify@example.com","username":"verify_user","password":"strong-password-123"})
assert signup.status_code==302
uid=one("SELECT id FROM users WHERE username='verify_user'")["id"]

token=csrf("/vendor")
store_apply=client.post("/stores/apply",data={"_csrf":token,"name":"Verify Outfit Store","description":"Smoke test store","contact_email":"store@example.com","contact_phone":"03001234567"})
assert store_apply.status_code==302
store=one("SELECT * FROM stores WHERE owner_user_id=:u",{"u":uid})
assert store and store["status"]=="pending_review"
assert client.get("/vendor").status_code==200

# Duplicate signup must be rejected, not treated as success.
token=csrf()
dup=client.post("/signup",data={"_csrf":token,"full_name":"Verify User 2","email":"verify@example.com","username":"verify_user","password":"strong-password-123"})
assert dup.status_code==200
assert "already in use" in dup.get_data(as_text=True)

# Profile route is functional and protected by CSRF.
assert client.get("/profile").status_code==200
token=csrf("/profile")
profile=client.post("/profile",data={"_csrf":token,"full_name":"Verify User Updated","email":"verify@example.com","username":"verify_user","password":""})
assert profile.status_code==200
assert one("SELECT full_name FROM users WHERE id=:u",{"u":uid})["full_name"]=="Verify User Updated"

# Cart and checkout.
token=csrf()
add=client.post("/cart/add/1",data={"_csrf":token,"quantity":"2","size":"M","color":"Black"})
assert add.status_code==302
assert int(one("SELECT quantity FROM cart_items WHERE user_id=:u AND product_id=1",{"u":uid})["quantity"])==2

# Invalid variant is rejected.
token=csrf()
bad_variant=client.post("/cart/add/1",data={"_csrf":token,"quantity":"1","size":"INVALID","color":"Black"})
assert bad_variant.status_code==400

checkout=client.get("/checkout")
assert checkout.status_code==200
token=csrf("/checkout")
placed=client.post("/checkout",data={"_csrf":token,"full_name":"Verify User","phone":"03001234567","province":"Sindh","area":"Gulshan","address":"1 Verification Street","city":"Karachi","postal_code":"74000","instructions":"","payment_method":"easypaisa","transaction_ref":"VERIFY-12345","payment_proof":(BytesIO(__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")),"proof.png")})
assert placed.status_code==302
order_page=client.get(placed.location)
assert order_page.status_code==200
assert "YM-" in order_page.get_data(as_text=True)
order_id=int(placed.location.rsplit("/",1)[-1])

product=one("SELECT stock FROM products WHERE id=1")
assert int(product["stock"])==36
assert int(one("SELECT COUNT(*) n FROM orders WHERE user_id=:u",{"u":uid})["n"])==1
payment=one("SELECT method,status FROM payments ORDER BY id DESC LIMIT 1")
assert payment["method"]=="Easypaisa" and payment["status"]=="Pending Verification"

# Transaction references are checked case-insensitively, including legacy lowercase values.
before_duplicate_orders=int(one("SELECT COUNT(*) n FROM orders")["n"])
token=csrf("/shop")
assert client.post("/cart/add/1",data={"_csrf":token,"quantity":"1","size":"M","color":"Black"}).status_code==302
token=csrf("/checkout")
duplicate_case=client.post("/checkout",data={"_csrf":token,"full_name":"Verify User","phone":"03001234567","province":"Sindh","area":"Gulshan","address":"1 Verification Street","city":"Karachi","payment_method":"easypaisa","transaction_ref":"verify-12345","payment_proof":(BytesIO(__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")),"duplicate.png")})
assert duplicate_case.status_code==200
assert "already been submitted" in duplicate_case.get_data(as_text=True)
assert int(one("SELECT COUNT(*) n FROM orders")["n"])==before_duplicate_orders
with engine.begin() as c:
    c.execute(text("DELETE FROM cart_items WHERE user_id=:u"),{"u":uid})

# Customer cannot access admin or superadmin.
assert client.get("/admin").status_code in (302,403)
assert client.get("/superadmin").status_code in (302,403)

admin_client=app.test_client()
token=csrf("/admin-login",admin_client)
assert admin_client.post("/admin-login",data={"_csrf":token,"username":"verify_admin","password":"AdminPass123!"}).status_code==302
token=csrf("/admin",admin_client)
approved=admin_client.post(f"/admin/store/{store['id']}/status",data={"_csrf":token,"status":"approved"})
assert approved.status_code==302
assert one("SELECT status FROM stores WHERE id=:s",{"s":store["id"]})["status"]=="approved"
owner_client=app.test_client()
token=csrf("/login",owner_client)
assert owner_client.post("/login",data={"_csrf":token,"username":"verify_user","password":"strong-password-123"}).status_code==302
token=csrf("/vendor",owner_client)
assert owner_client.post("/vendor/product",data={"_csrf":token,"name":"Vendor Test Product","price":"1000","stock":"5","sizes":"S,M,L","colors":"Black","image_url":"","description":"Vendor isolation smoke test"}).status_code==302
vendor_product=one("SELECT * FROM products WHERE name='Vendor Test Product'")
assert vendor_product and vendor_product["store_id"]==store["id"]
assert owner_client.get(f"/stores/{store['slug']}").status_code==200
# Vendor ownership checks reject attempts to edit platform-owned products.
token=csrf("/vendor",owner_client)
assert owner_client.post("/vendor/product",data={"_csrf":token,"id":"1","name":"Hijacked Product","price":"1","stock":"99"}).status_code==404
# Mixed-store checkout is rejected instead of creating an incorrectly fulfilled order.
token=csrf("/shop",owner_client)
assert owner_client.post("/cart/add/1",data={"_csrf":token,"quantity":"1","size":"M","color":"Black"}).status_code==302
token=csrf("/shop",owner_client)
assert owner_client.post(f"/cart/add/{vendor_product['id']}",data={"_csrf":token,"quantity":"1","size":"S","color":"Black"}).status_code==302
mixed_checkout=owner_client.get("/checkout",follow_redirects=True)
assert mixed_checkout.status_code==200
assert "different stores" in mixed_checkout.get_data(as_text=True)
# Vendor can archive only its own products; archived listings disappear from the public catalog.
token=csrf("/vendor",owner_client)
archived=owner_client.post(f"/vendor/product/{vendor_product['id']}/archive",data={"_csrf":token})
assert archived.status_code==302
assert one("SELECT status,stock FROM products WHERE id=:p",{"p":vendor_product["id"]})["status"]=="archived"
assert int(one("SELECT stock FROM products WHERE id=:p",{"p":vendor_product["id"]})["stock"])==0
assert owner_client.get(f"/product/{vendor_product['slug']}").status_code==404
# Try-On must not present a generation form when no real provider is configured.
tryon_page=owner_client.get("/try-on/aero-oversized-tee")
assert tryon_page.status_code==200
assert "not configured" in tryon_page.get_data(as_text=True).lower()
assert "Generate AI Try-On" not in tryon_page.get_data(as_text=True)
# Disabled customers cannot authenticate.
from app.main import engine
from sqlalchemy import text
with engine.begin() as c:
    c.execute(text("UPDATE users SET is_active=0 WHERE id=:u"),{"u":uid})
disabled_client=app.test_client()
token=csrf("/login",disabled_client)
disabled_login=disabled_client.post("/login",data={"_csrf":token,"username":"verify_user","password":"strong-password-123"})
assert disabled_login.status_code==200
with engine.begin() as c:
    c.execute(text("UPDATE users SET is_active=1 WHERE id=:u"),{"u":uid})

# Customer #2 places an order; Customer #1 cannot access it.
client2=app.test_client()
token=csrf("/signup",client2)
signup2=client2.post("/signup",data={"_csrf":token,"full_name":"Second Verify User","email":"verify2@example.com","username":"verify_user_2","password":"strong-password-456"})
assert signup2.status_code==302
token=csrf("/vendor",client2)
assert client2.post("/vendor/product",data={"_csrf":token,"name":"Unauthorized Product","price":"1000","stock":"1"}).status_code==403
token=csrf("/shop",client2)
assert client2.post("/cart/add/1",data={"_csrf":token,"quantity":"1","size":"M","color":"Black"}).status_code==302
token=csrf("/checkout",client2)
placed2=client2.post("/checkout",data={"_csrf":token,"full_name":"Second Verify User","phone":"03001234568","province":"Sindh","area":"Gulshan","address":"2 Verification Street","city":"Karachi","postal_code":"74000","instructions":"","payment_method":"easypaisa","transaction_ref":"VERIFY-12346","payment_proof":(BytesIO(__import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")),"proof2.png")})
assert placed2.status_code==302
other_order_id=int(placed2.location.rsplit("/",1)[-1])
assert client.get(f"/orders/{order_id}").status_code==200
assert client.get(f"/orders/{other_order_id}").status_code==404
assert client2.get(f"/orders/{other_order_id}").status_code==200
# Payment proofs are private and a customer cannot fetch the admin review endpoint.
payment_id=int(one("SELECT id FROM payments WHERE order_id=:o",{"o":other_order_id})["id"])
assert client2.get(f"/admin/payment-proof/{payment_id}").status_code==302
# Cancellation restores stock exactly once and cannot be replayed to inflate inventory.
stock_before_cancel=int(one("SELECT stock FROM products WHERE id=1")["stock"])
token=csrf(f"/orders/{other_order_id}",client2)
assert client2.post(f"/orders/{other_order_id}/cancel",data={"_csrf":token}).status_code==302
stock_after_cancel=int(one("SELECT stock FROM products WHERE id=1")["stock"])
assert stock_after_cancel==stock_before_cancel+1
token=csrf(f"/orders/{other_order_id}",client2)
assert client2.post(f"/orders/{other_order_id}/cancel",data={"_csrf":token}).status_code==400
assert int(one("SELECT stock FROM products WHERE id=1")["stock"])==stock_after_cancel

# Wishlist.
token=csrf()
assert client.post("/wishlist/toggle/1",data={"_csrf":token}).status_code==302
assert one("SELECT id FROM wishlist WHERE user_id=:u AND product_id=1",{"u":uid})

# Admin login and permission boundary.
client=app.test_client()
token=csrf("/admin-login")
admin_login=client.post("/admin-login",data={"_csrf":token,"username":"verify_admin","password":"AdminPass123!"})
assert admin_login.status_code==302
assert client.get("/admin").status_code==200
# Payment review is an atomic one-time transition; a second reviewer cannot overwrite it.
first_payment=one("SELECT id,order_id FROM payments WHERE transaction_ref='VERIFY-12345'")
token=csrf("/admin",client)
reviewed=client.post(f"/admin/payment/{first_payment['id']}",data={"_csrf":token,"status":"Verified","reason":"Smoke-test review"})
assert reviewed.status_code==302
assert one("SELECT status FROM payments WHERE id=:p",{"p":first_payment["id"]})["status"]=="Verified"
assert one("SELECT payment_status,status FROM orders WHERE id=:o",{"o":first_payment["order_id"]})["payment_status"]=="Verified"
token=csrf("/admin",client)
review_again=client.post(f"/admin/payment/{first_payment['id']}",data={"_csrf":token,"status":"Rejected","reason":"Must not overwrite"})
assert review_again.status_code==400
# Admin cancellation of a verified order starts a manual refund; marking refunded updates payment state.
token=csrf("/admin",client)
admin_cancel=client.post(f"/admin/order/{first_payment['order_id']}",data={"_csrf":token,"status":"Cancelled"})
assert admin_cancel.status_code==302
assert one("SELECT payment_status FROM orders WHERE id=:o",{"o":first_payment["order_id"]})["payment_status"]=="Refund Pending"
assert one("SELECT status FROM payments WHERE id=:p",{"p":first_payment["id"]})["status"]=="Refund Pending"
token=csrf("/admin",client)
admin_refund=client.post(f"/admin/order/{first_payment['order_id']}",data={"_csrf":token,"status":"Refunded"})
assert admin_refund.status_code==302
assert one("SELECT payment_status,status FROM orders WHERE id=:o",{"o":first_payment["order_id"]})["payment_status"]=="Refunded"
assert one("SELECT status FROM payments WHERE id=:p",{"p":first_payment["id"]})["status"]=="Refunded"
# Inventory adjustments are atomic and cannot make stock negative.
stock_before_invalid=int(one("SELECT stock FROM products WHERE id=1")["stock"])
token=csrf("/admin",client)
invalid_inventory=client.post("/admin/inventory/1",data={"_csrf":token,"change":"-999999","reason":"negative stock test"})
assert invalid_inventory.status_code==400
assert int(one("SELECT stock FROM products WHERE id=1")["stock"])==stock_before_invalid
assert client.get("/superadmin").status_code in (302,403)

# Superadmin login.
client=app.test_client()
token=csrf("/admin-login")
super_login=client.post("/admin-login",data={"_csrf":token,"username":"verify_super","password":"SuperPass123!"})
assert super_login.status_code==302
assert client.get("/superadmin").status_code==200

# Superadmin-created standard admins must not receive settings permission by default.
token=csrf("/superadmin",client)
created_admin=client.post("/superadmin/admin",data={"_csrf":token,"full_name":"Created Admin","username":"created_admin","email":"created-admin@example.com","password":"CreatedAdminPass123!","role":"admin"})
assert created_admin.status_code==302
created_admin_id=one("SELECT id FROM admins WHERE username='created_admin'")["id"]
assert not one("SELECT id FROM admin_permissions WHERE admin_id=:a AND permission='manage_settings'",{"a":created_admin_id})
# A report-only administrator must not receive customer/payment/product management data or permissions.
with engine.begin() as c:
    limited_admin_id=c.execute(text("""INSERT INTO admins(username,email,full_name,password_hash,role)
        VALUES('limited_admin','limited@example.com','Limited Admin',:p,'admin') RETURNING id"""),
        {"p":generate_password_hash("LimitedAdminPass123!")}).scalar_one()
    c.execute(text("INSERT INTO admin_permissions(admin_id,permission) VALUES(:a,'view_reports')"),{"a":limited_admin_id})
limited_client=app.test_client()
token=csrf("/admin-login",limited_client)
assert limited_client.post("/admin-login",data={"_csrf":token,"username":"limited_admin","password":"LimitedAdminPass123!"}).status_code==302
dashboard=limited_client.get("/admin")
assert dashboard.status_code==200
dashboard_html=dashboard.get_data(as_text=True)
assert "Analytics" in dashboard_html
assert "Payment verification" not in dashboard_html
assert "Save product" not in dashboard_html
assert 'href="/admin/customers"' not in dashboard_html
token=csrf("/admin",limited_client)
assert limited_client.post("/admin/product",data={"_csrf":token,"name":"No Permission","category":"Other","price":"10","stock":"1"}).status_code==403
assert limited_client.post(f"/admin/payment/{first_payment['id']}",data={"_csrf":token,"status":"Verified"}).status_code==403
assert limited_client.get(f"/admin/payment-proof/{first_payment['id']}").status_code==403

# JWT API token protection, refresh rotation, replay rejection and logout.
api_client=app.test_client()
api_token=api_client.get("/api/auth/csrf").json["csrf_token"]
api_headers={"X-CSRFToken":api_token}
api_signup=api_client.post("/api/auth/signup",json={"full_name":"JWT Verify User","email":"jwtverify@example.com","username":"jwt_verify_user","password":"jwt-strong-password-123"},headers=api_headers)
assert api_signup.status_code==201,api_signup.get_data(as_text=True)
access=api_signup.json["access_token"]; refresh=api_signup.json["refresh_token"]
assert api_client.get("/api/v1/me").status_code==401
assert api_client.get("/api/v1/me",headers={"Authorization":f"Bearer {access}"}).json["user"]["username"]=="jwt_verify_user"
rotated=api_client.post("/api/auth/refresh",json={"refresh_token":refresh},headers=api_headers)
assert rotated.status_code==200,rotated.get_data(as_text=True)
assert api_client.post("/api/auth/refresh",json={"refresh_token":refresh},headers=api_headers).status_code==401
new_refresh=rotated.json["refresh_token"]
assert api_client.post("/api/auth/logout",json={"refresh_token":new_refresh},headers=api_headers).status_code==200
assert api_client.post("/api/auth/refresh",json={"refresh_token":new_refresh},headers=api_headers).status_code==401

# AI assistant is database-grounded and remains usable without an external AI key.
client=app.test_client()
token=csrf("/signup")  # only to establish a session/CSRF; signup page is public
assistant=client.post("/api/assistant",json={"message":"black shirt under 5000"},headers={"X-CSRFToken":token})
assert assistant.status_code==200
assert all("name" in p and "price" in p and "slug" in p for p in assistant.json["products"])
# Draft/archived products must not leak into catalog assistant results.
with engine.begin() as c:
    c.execute(text("""INSERT INTO products(name,slug,brand,category,description,price,original_price,discount,stock,sizes,colors,rating,review_count,tags,image_url,status,featured)
        VALUES('Hidden Draft Catalog Item','hidden-draft-catalog-item','Private','Other / Accessories','draft only',1,1,0,1,'One Size','Black',5,1,'black shirt',:img,'draft',0)"""),
        {"img":"https://example.com/draft.jpg"})
draft_assistant=client.post("/api/assistant",json={"message":"black shirt"},headers={"X-CSRFToken":token})
assert draft_assistant.status_code==200
assert all(p["slug"]!="hidden-draft-catalog-item" for p in draft_assistant.json["products"])
# A mocked LLM response containing a fabricated product/price is rejected in favour of verified catalog text.
import requests
from unittest.mock import patch
class _FakeLLMResponse:
    ok=True
    def json(self):
        return {"choices":[{"message":{"content":"Buy Unicorn Jacket for Rs. 1; it is in stock."}}]}
os.environ["AI_ASSISTANT_API_KEY"]="test-key"
os.environ["AI_ASSISTANT_API_URL"]="https://example.invalid/v1/chat/completions"
os.environ["AI_ASSISTANT_MODEL"]="test-model"
token=csrf("/signup")
with patch("requests.post",return_value=_FakeLLMResponse()):
    guarded=client.post("/api/assistant",json={"message":"black shirt under 5000"},headers={"X-CSRFToken":token})
assert guarded.status_code==200
assert "Unicorn Jacket" not in guarded.json["reply"]
assert "Rs. 1" not in guarded.json["reply"]
for _key in ("AI_ASSISTANT_API_KEY","AI_ASSISTANT_API_URL","AI_ASSISTANT_MODEL"):
    os.environ.pop(_key,None)
with engine.begin() as c:
    c.execute(text("DELETE FROM products WHERE slug='hidden-draft-catalog-item'"))

print("Yours Mart production smoke verification passed.")
engine.dispose()
_VERIFY_TEMP.cleanup()
