import os
os.environ.setdefault("DATABASE_URL","sqlite:///verify_yours_mart.db")
os.environ.setdefault("SECRET_KEY","verify-secret")
from app import app
client=app.test_client()
for path in ["/","/shop","/health","/login","/signup","/admin-login"]:
    r=client.get(path)
    assert r.status_code < 500, (path,r.status_code)
assert client.get("/health").json["status"]=="ok"
print("Yours Mart smoke verification passed.")
try: os.remove("verify_yours_mart.db")
except FileNotFoundError: pass
