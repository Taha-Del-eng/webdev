import os, json, math, re, secrets, uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash, send_file
from sqlalchemy import create_engine, text, event
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from urllib.parse import urlparse
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from .services.ai_tryon import generate_virtual_tryon, get_virtual_tryon_status, TryOnError
from .services.recommendations import recommend
from .services.storage import upload_file

load_dotenv()
BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///yours_mart.db")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql+psycopg://",1)
elif DATABASE_URL.startswith("postgresql://"): DATABASE_URL=DATABASE_URL.replace("postgresql://","postgresql+psycopg://",1)
engine=create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {})
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine,"connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor=dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
app=Flask(__name__, template_folder=os.path.join(BASE_DIR,"templates"), static_folder=os.path.join(BASE_DIR,"static"))
secret_key=os.getenv("SECRET_KEY")
if not secret_key and (os.getenv("VERCEL")=="1" or os.getenv("FLASK_ENV")=="production"):
    raise RuntimeError("SECRET_KEY must be configured in production.")
secure_cookie=os.getenv("SESSION_COOKIE_SECURE")
if secure_cookie is None:
    secure_cookie=os.getenv("VERCEL")=="1"
app.config.update(SECRET_KEY=secret_key or secrets.token_hex(32), MAX_CONTENT_LENGTH=8*1024*1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=str(secure_cookie).lower() in {"1","true","yes"},
                  PERMANENT_SESSION_LIFETIME=timedelta(days=14))
CATEGORIES=["Men / T-Shirts","Men / Shirts","Men / Polo Shirts","Men / Hoodies","Men / Sweatshirts","Men / Jackets","Men / Jeans","Men / Trousers","Men / Kurta","Men / Shalwar Kameez","Men / Formal Wear","Women / Dresses","Women / Tops","Women / Shirts","Women / Abayas","Women / Hijabs","Women / Trousers","Women / Jeans","Women / Kurtis","Women / Formal Wear","Other / Shoes","Other / Watches","Other / Bags","Other / Belts","Other / Jewelry","Other / Accessories"]

SEED=[
("Aero Oversized Tee","Aster","Men / T-Shirts","2499","3499",38,"S,M,L,XL","Black,White","4.8",126,"oversized,casual,streetwear", "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85"),
("Essential Oxford Shirt","Northline","Men / Shirts","3999","4999",24,"S,M,L,XL","White,Sky Blue","4.7",84,"smart,office,classic", "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=900&q=85"),
("Core Polo","Monarch","Men / Polo Shirts","3299","3999",31,"S,M,L,XL","Navy,Black","4.6",93,"polo,smart-casual,weekend", "https://images.unsplash.com/photo-1625910513413-5fc45f7d9b35?auto=format&fit=crop&w=900&q=85"),
("Cloud Fleece Hoodie","Aster","Men / Hoodies","4499","5999",19,"S,M,L,XL","Charcoal,Cream","4.9",71,"hoodie,cozy,streetwear", "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=85"),
("Midnight Denim","Northline","Men / Jeans","4999","6499",16,"30,32,34,36","Black,Indigo","4.7",58,"jeans,denim,black", "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=900&q=85"),
("Urban Bomber","Monarch","Men / Jackets","6499","7999",12,"S,M,L,XL","Black,Olive","4.8",44,"jacket,bomber,streetwear", "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=85"),
("Luna Midi Dress","Velora","Women / Dresses","5499","6999",14,"S,M,L","Black,Burgundy","4.8",112,"dress,date-night,formal", "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85"),
("Satin Ease Top","Velora","Women / Tops","2999","3799",27,"S,M,L","Ivory,Black","4.6",63,"top,satin,date", "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?auto=format&fit=crop&w=900&q=85"),
("Noir Abaya","Riva","Women / Abayas","6999","8499",10,"S,M,L,XL","Black","4.9",51,"abaya,elegant,modest", "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=900&q=85"),
("Everyday Kurti","Riva","Women / Kurtis","2899","3499",22,"S,M,L,XL","Sage,Black","4.5",39,"kurti,casual,everyday", "https://images.unsplash.com/photo-1610030469668-8e8f0b7f6a0b?auto=format&fit=crop&w=900&q=85"),
("Classic Runner","Solecraft","Other / Shoes","5999","7499",18,"39,40,41,42,43,44","White,Black","4.7",98,"shoes,sneakers,casual", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85"),
("Minimal Steel Watch","Chrona","Other / Watches","7999","9999",8,"One Size","Silver,Black","4.8",76,"watch,minimal,formal", "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85"),
("Metro Crossbody","Noma","Other / Bags","4499","5799",15,"One Size","Black,Tan","4.6",47,"bag,crossbody,travel", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85"),
("Leather Line Belt","Noma","Other / Belts","1799","2299",33,"30,32,34,36,38","Black,Brown","4.5",28,"belt,leather,classic", "https://images.unsplash.com/photo-1624222247344-550fb60583dc?auto=format&fit=crop&w=900&q=85"),
("Aura Chain","Veyra","Other / Jewelry","2299","2999",25,"One Size","Gold,Silver","4.7",55,"jewelry,chain,minimal", "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=900&q=85"),
("Everyday Cap","Monarch","Other / Accessories","1299","1699",40,"One Size","Black,Navy","4.4",19,"cap,accessory,casual", "https://images.unsplash.com/photo-1521369909029-2afed882baee?auto=format&fit=crop&w=900&q=85"),
("Executive Blazer","Northline","Men / Formal Wear","8999","10999",7,"S,M,L,XL","Black,Charcoal","4.9",33,"formal,blazer,wedding", "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=900&q=85"),
("Noir Straight Jeans","Velora","Women / Jeans","4799","5999",13,"28,30,32,34","Black,Blue","4.6",42,"jeans,denim,black,casual", "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=85")
]

def db():
    return engine.connect()

def parse_int(value, default=0, minimum=None, maximum=None):
    try:
        n=int(str(value).strip())
    except (TypeError, ValueError):
        n=default
    if minimum is not None: n=max(minimum,n)
    if maximum is not None: n=min(maximum,n)
    return n

def parse_money(value, default=0.0, minimum=0.0, maximum=999999999.0):
    try:
        n=float(str(value).replace(",","").strip())
    except (TypeError, ValueError):
        n=default
    if not math.isfinite(n): n=default
    return max(minimum,min(maximum,n))

def csv_values(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]

def valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", value or ""))

def init_db():
    ddl=[
    """CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, full_name VARCHAR(120) NOT NULL, email VARCHAR(180) UNIQUE NOT NULL, username VARCHAR(80) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, name VARCHAR(120) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, name VARCHAR(180) NOT NULL, slug VARCHAR(220) UNIQUE NOT NULL, brand VARCHAR(120), category VARCHAR(120) NOT NULL, description TEXT, price NUMERIC(12,2) NOT NULL CHECK(price>0), original_price NUMERIC(12,2), discount NUMERIC(5,2) DEFAULT 0, stock INTEGER DEFAULT 0 CHECK(stock>=0), sizes TEXT, colors TEXT, rating NUMERIC(3,2) DEFAULT 0 CHECK(rating>=0 AND rating<=5), review_count INTEGER DEFAULT 0, tags TEXT, image_url TEXT NOT NULL, additional_images TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS cart_items(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, quantity INTEGER NOT NULL CHECK(quantity>0), size VARCHAR(30), color VARCHAR(50), UNIQUE(user_id,product_id,size,color))""",
    """CREATE TABLE IF NOT EXISTS wishlist(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, UNIQUE(user_id,product_id))""",
    """CREATE TABLE IF NOT EXISTS addresses(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, full_name VARCHAR(120), phone VARCHAR(40), address TEXT, city VARCHAR(80), postal_code VARCHAR(30), instructions TEXT)""",
    """CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT, total NUMERIC(12,2) NOT NULL CHECK(total>=0), shipping_address TEXT NOT NULL, payment_method VARCHAR(40) DEFAULT 'COD', payment_status VARCHAR(40) DEFAULT 'Pending', status VARCHAR(40) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, quantity INTEGER NOT NULL CHECK(quantity>0), price NUMERIC(12,2) NOT NULL CHECK(price>=0), size VARCHAR(30), color VARCHAR(50))""",
    """CREATE TABLE IF NOT EXISTS tryon_history(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, job_id VARCHAR(255), status VARCHAR(40), result_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS categories_meta(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, name VARCHAR(120) UNIQUE NOT NULL)"""
    ]

    iddef = "INTEGER PRIMARY KEY AUTOINCREMENT" if IS_SQLITE else "BIGSERIAL PRIMARY KEY"
    ddl.extend([
    f"""CREATE TABLE IF NOT EXISTS admins(id {iddef}, username VARCHAR(80) UNIQUE NOT NULL, email VARCHAR(180) UNIQUE NOT NULL, full_name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'admin', is_active INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    f"""CREATE TABLE IF NOT EXISTS admin_permissions(id {iddef}, admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE, permission VARCHAR(80) NOT NULL, UNIQUE(admin_id,permission))""",
    f"""CREATE TABLE IF NOT EXISTS payments(id {iddef}, order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE, method VARCHAR(40) NOT NULL, amount NUMERIC(12,2) NOT NULL, transaction_ref VARCHAR(120), proof_path TEXT, status VARCHAR(40) NOT NULL DEFAULT 'Pending Verification', rejection_reason TEXT, verified_by INTEGER REFERENCES admins(id) ON DELETE SET NULL, verified_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    f"""CREATE TABLE IF NOT EXISTS inventory_transactions(id {iddef}, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL, change_qty INTEGER NOT NULL, stock_after INTEGER NOT NULL, reason VARCHAR(160), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    f"""CREATE TABLE IF NOT EXISTS reviews(id {iddef}, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), body TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,product_id,order_id))""",
    f"""CREATE TABLE IF NOT EXISTS audit_logs(id {iddef}, admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL, action VARCHAR(120) NOT NULL, target_type VARCHAR(60), target_id VARCHAR(80), details TEXT, ip_address VARCHAR(80), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    ])
    with engine.begin() as c:
        for q in ddl:
            try: c.execute(text(q))
            except Exception:
                if "GENERATED ALWAYS AS IDENTITY" in q:
                    c.execute(text(q.replace("INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY","INTEGER PRIMARY KEY AUTOINCREMENT")))
                else: raise
        migrations = [
            ("users","role","VARCHAR(20) DEFAULT 'customer'"),("users","is_active","INTEGER DEFAULT 1"),("users","updated_at","TIMESTAMP"),
            ("products","min_stock","INTEGER DEFAULT 5"),("products","status","VARCHAR(20) DEFAULT 'active'"),("products","featured","INTEGER DEFAULT 0"),
            ("orders","order_number","VARCHAR(40)"),("orders","subtotal","NUMERIC(12,2) DEFAULT 0"),("orders","discount","NUMERIC(12,2) DEFAULT 0"),("orders","shipping_fee","NUMERIC(12,2) DEFAULT 0"),("orders","updated_at","TIMESTAMP"),
            ("addresses","province","VARCHAR(80)"),("addresses","area","VARCHAR(120)"),("addresses","is_default","INTEGER DEFAULT 0"),
        ]
        for table,col,typ in migrations:
            try: c.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
            except Exception: pass
        try: c.execute(text("UPDATE orders SET order_number='YM-' || printf('%06d',id) WHERE order_number IS NULL OR order_number=''"))
        except Exception: pass
        try: c.execute(text("UPDATE orders SET subtotal=total WHERE subtotal IS NULL OR subtotal=0"))
        except Exception: pass
        su=os.getenv("SUPERADMIN_USERNAME"); sh=os.getenv("SUPERADMIN_PASSWORD_HASH")
        au=os.getenv("ADMIN_USERNAME"); ah=os.getenv("ADMIN_PASSWORD_HASH")
        if su and sh and not c.execute(text("SELECT 1 FROM admins WHERE username=:u"),{"u":su}).first():
            c.execute(text("INSERT INTO admins(username,email,full_name,password_hash,role) VALUES(:u,:e,:n,:p,'superadmin')"),{"u":su,"e":os.getenv("SUPERADMIN_EMAIL",f"{su}@yoursmart.local"),"n":os.getenv("SUPERADMIN_NAME","Yours Mart Superadmin"),"p":sh})
        if au and ah and not c.execute(text("SELECT 1 FROM admins WHERE username=:u"),{"u":au}).first():
            c.execute(text("INSERT INTO admins(username,email,full_name,password_hash,role) VALUES(:u,:e,:n,:p,'admin')"),{"u":au,"e":os.getenv("ADMIN_EMAIL",f"{au}@yoursmart.local"),"n":os.getenv("ADMIN_NAME","Yours Mart Admin"),"p":ah})
        for a in c.execute(text("SELECT id,role FROM admins")).fetchall():
            perms={"manage_products","manage_orders","manage_inventory","manage_customers","manage_payments","view_reports","manage_settings"} if a[1]=="superadmin" else {"manage_products","manage_orders","manage_inventory","manage_customers","manage_payments","view_reports"}
            for perm in perms:
                try:c.execute(text("INSERT INTO admin_permissions(admin_id,permission) VALUES(:a,:p)"),{"a":a[0],"p":perm})
                except Exception:pass
        count=c.execute(text("SELECT COUNT(*) FROM products")).scalar()
        if not count:
            for name in CATEGORIES: c.execute(text("INSERT INTO categories(name) VALUES(:n) ON CONFLICT DO NOTHING"),{"n":name})
            for p in SEED:
                slug=re.sub(r"[^a-z0-9]+","-",p[0].lower()).strip("-")
                c.execute(text("""INSERT INTO products(name,slug,brand,category,description,price,original_price,discount,stock,sizes,colors,rating,review_count,tags,image_url,additional_images)
                VALUES(:name,:slug,:brand,:cat,:desc,:price,:orig,:disc,:stock,:sizes,:colors,:rating,:reviews,:tags,:image,:additional)"""),
                dict(name=p[0],slug=slug,brand=p[1],cat=p[2],desc=f"{p[0]} by {p[1]}. Curated for everyday style with premium materials and an easy-to-wear silhouette.",price=float(p[3]),orig=float(p[4]),disc=round((1-float(p[3])/float(p[4]))*100,1),stock=p[5],sizes=p[6],colors=p[7],rating=float(p[8]),reviews=p[9],tags=p[10],image=p[11],additional=json.dumps([p[11]])))
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
            "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)",
            "CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id,created_at)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_tryon_user_created ON tryon_history(user_id,created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tryon_job_user ON tryon_history(job_id,user_id)"
        ]:
            c.execute(text(idx))
        admin=os.getenv("ADMIN_USERNAME")
        if admin and not c.execute(text("SELECT id FROM users WHERE username=:u"),{"u":admin}).first():
            pass

init_db()

def rows(sql, params={}):
    with db() as c: return [dict(r._mapping) for r in c.execute(text(sql),params).fetchall()]
def one(sql,params={}):
    with db() as c:
        r=c.execute(text(sql),params).first()
        return dict(r._mapping) if r else None

def csrf_token():
    if "csrf" not in session: session["csrf"]=secrets.token_urlsafe(24)
    return session["csrf"]
app.jinja_env.globals["csrf_token"]=csrf_token

@app.before_request
def protect():
    if request.method=="POST":
        token=request.headers.get("X-CSRFToken") or request.form.get("_csrf")
        if not token or not secrets.compare_digest(token,session.get("csrf","")): abort(400,"Invalid CSRF token.")

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("X-Frame-Options","DENY")
    response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
    if request.is_secure or os.getenv("VERCEL")=="1":
        response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
    return response

@app.context_processor
def context():
    count=0
    if session.get("user_id"):
        count=one("SELECT COALESCE(SUM(quantity),0) n FROM cart_items WHERE user_id=:u",{"u":session["user_id"]})["n"]
    return {"cart_count":count,"current_user":one("SELECT id,full_name,username FROM users WHERE id=:u",{"u":session.get("user_id")}) if session.get("user_id") else None}

def login_required(f):
    @wraps(f)
    def w(*a,**k):
        uid=session.get("user_id")
        if not uid: return redirect(url_for("login"))
        if not one("SELECT id FROM users WHERE id=:u AND is_active=1",{"u":uid}):
            session.clear()
            return redirect(url_for("login"))
        return f(*a,**k)
    return w

def admin_required(permission=None, superadmin=False):
    def deco(f):
        @wraps(f)
        def w(*a,**k):
            aid=session.get("admin_id")
            if not aid:return redirect(url_for("admin_login"))
            arow=one("SELECT * FROM admins WHERE id=:i AND is_active=1",{"i":aid})
            if not arow:
                session.clear()
                return redirect(url_for("admin_login"))
            if superadmin and arow["role"]!="superadmin":abort(403)
            if permission and arow["role"]!="superadmin":
                ok=one("SELECT id FROM admin_permissions WHERE admin_id=:a AND permission=:p",{"a":aid,"p":permission})
                if not ok:abort(403)
            return f(*a,**k)
        return w
    return deco

def admin_audit(action,target_type=None,target_id=None,details=""):
    aid=session.get("admin_id")
    if not aid:return
    try:
        with engine.begin() as c:
            c.execute(text("INSERT INTO audit_logs(admin_id,action,target_type,target_id,details,ip_address) VALUES(:a,:x,:t,:i,:d,:ip)"),
                      {"a":aid,"x":action,"t":target_type,"i":str(target_id) if target_id is not None else None,"d":details[:1000],"ip":request.headers.get("X-Forwarded-For",request.remote_addr)})
    except Exception:pass

def product_dict(p):
    if not p:return None
    for k in ("sizes","colors","tags"): p[k]=(p.get(k) or "").split(",") if p.get(k) else []
    try:p["additional_images"]=json.loads(p.get("additional_images") or "[]")
    except: p["additional_images"]=[]
    return p

def product_query(where="",params={},order="p.created_at DESC",limit=None,offset=0):
    lim=f" LIMIT {int(limit)} OFFSET {int(offset)}" if limit else ""
    return [product_dict(x) for x in rows(f"SELECT p.* FROM products p {where} ORDER BY {order}{lim}",params)]

@app.get("/")
def home():
    trending=product_query(order="p.rating DESC, p.review_count DESC",limit=4)
    new_arrivals=product_query(order="p.created_at DESC",limit=4)
    best_sellers=product_query(order="p.review_count DESC, p.rating DESC",limit=4)
    recommended=product_query(order="p.rating DESC, p.created_at DESC",limit=4)
    return render_template("landing.html",trending=trending,new_arrivals=new_arrivals,best_sellers=best_sellers,categories=rows("SELECT * FROM categories ORDER BY name"),recommended=recommended)

@app.get("/shop")
def shop():
    q=request.args.get("q","").strip(); cat=request.args.get("category","").strip(); brand=request.args.get("brand","").strip()
    color=request.args.get("color","").strip(); size=request.args.get("size","").strip(); rating=request.args.get("rating","").strip()
    minp=request.args.get("min","").strip(); maxp=request.args.get("max","").strip(); sort=request.args.get("sort","newest")
    page=parse_int(request.args.get("page",1),1,1,100000); per=12
    try: min_value=float(minp) if minp else None
    except ValueError: min_value=None; minp=""
    try: max_value=float(maxp) if maxp else None
    except ValueError: max_value=None; maxp=""
    cond=[]; par={}
    if q: cond.append("(LOWER(p.name) LIKE LOWER(:q) OR LOWER(p.brand) LIKE LOWER(:q) OR LOWER(p.category) LIKE LOWER(:q) OR LOWER(p.description) LIKE LOWER(:q) OR LOWER(p.tags) LIKE LOWER(:q) OR LOWER(p.colors) LIKE LOWER(:q))"); par["q"]=f"%{q}%"
    if cat: cond.append("p.category=:cat"); par["cat"]=cat
    if brand: cond.append("p.brand=:brand"); par["brand"]=brand
    if color: cond.append("LOWER(p.colors) LIKE LOWER(:color)"); par["color"]=f"%{color}%"
    if size: cond.append("p.sizes LIKE :size"); par["size"]=f"%{size}%"
    if rating: cond.append("p.rating>=:rating"); par["rating"]=float(rating)
    if min_value is not None and min_value>=0: cond.append("p.price>=:minp"); par["minp"]=min_value
    if max_value is not None and max_value>=0: cond.append("p.price<=:maxp"); par["maxp"]=max_value
    if min_value is not None and max_value is not None and min_value>max_value:
        min_value,max_value=max_value,min_value
        minp,maxp=str(min_value),str(max_value)
        cond=[c for c in cond if "p.price>=:minp" not in c and "p.price<=:maxp" not in c]
        par["minp"],par["maxp"]=min_value,max_value
        cond.extend(["p.price>=:minp","p.price<=:maxp"])
    where=("WHERE "+" AND ".join(cond)) if cond else ""
    order={"low":"p.price ASC","high":"p.price DESC","rating":"p.rating DESC","discount":"p.discount DESC","newest":"p.created_at DESC"}.get(sort,"p.created_at DESC")
    total=one(f"SELECT COUNT(*) n FROM products p {where}",par)["n"]
    products=product_query(where,par,order,per,(page-1)*per)
    return render_template("shop.html",products=products,total=total,page=page,per=per,q=q,category=cat,brand=brand,color=color,size=size,rating=rating,minp=minp,maxp=maxp,sort=sort,categories=rows("SELECT * FROM categories ORDER BY name"),brands=rows("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"),all_sizes=["XS","S","M","L","XL","28","30","32","34","36","38","40","41","42","43","44","One Size"])

@app.get("/product/<slug>")
def product(slug):
    p=product_dict(one("SELECT * FROM products WHERE slug=:s AND status='active'",{"s":slug}))
    if not p: abort(404)
    allp=product_query("WHERE p.status='active'",limit=40)
    reviews=rows("""SELECT r.rating,r.body,r.created_at,u.username
                    FROM reviews r JOIN users u ON u.id=r.user_id
                    WHERE r.product_id=:p ORDER BY r.created_at DESC LIMIT 50""",{"p":p["id"]})
    return render_template("product.html",product=p,reviews=reviews,similar=recommend(allp,p,4),complete=recommend(allp,{"id":-1,"category":p["category"],"price":p["price"],"tags":",".join(p["tags"])},4))

@app.post("/product/<int:pid>/review")
@login_required
def add_review(pid):
    if not one("SELECT id FROM products WHERE id=:p AND status='active'",{"p":pid}): abort(404)
    rating=parse_int(request.form.get("rating"),0,1,5)
    body=request.form.get("body","").strip()
    if rating<1 or len(body)>2000: abort(400,"Please provide a rating from 1 to 5 and review text under 2000 characters.")
    delivered=one("""SELECT oi.order_id FROM order_items oi JOIN orders o ON o.id=oi.order_id
                     WHERE o.user_id=:u AND oi.product_id=:p AND o.status='Delivered' LIMIT 1""",{"u":session["user_id"],"p":pid})
    if not delivered: abort(403,"You can review a product after a delivered order.")
    existing=one("SELECT id FROM reviews WHERE user_id=:u AND product_id=:p",{"u":session["user_id"],"p":pid})
    try:
        with engine.begin() as c:
            if existing:
                c.execute(text("UPDATE reviews SET rating=:r,body=:b WHERE id=:i"),{"r":rating,"b":body,"i":existing["id"]})
            else:
                c.execute(text("INSERT INTO reviews(user_id,product_id,order_id,rating,body) VALUES(:u,:p,:o,:r,:b)"),
                          {"u":session["user_id"],"p":pid,"o":delivered["order_id"],"r":rating,"b":body})
            c.execute(text("""UPDATE products SET rating=(SELECT COALESCE(AVG(rating),0) FROM reviews WHERE product_id=:p),
                              review_count=(SELECT COUNT(*) FROM reviews WHERE product_id=:p),
                              updated_at=CURRENT_TIMESTAMP WHERE id=:p"""),{"p":pid})
    except Exception:
        abort(400,"Your review could not be saved.")
    slug=one("SELECT slug FROM products WHERE id=:p",{"p":pid})["slug"]
    return redirect(url_for("product",slug=slug))

@app.route("/signup",methods=["GET","POST"])
def signup():
    if request.method=="POST":
        name,email,user,pwd=[request.form.get(x,"").strip() for x in ("full_name","email","username","password")]
        email=email.lower()
        if not name or len(name)>120: return render_template("auth.html",mode="signup",error="Please enter a valid full name.")
        if not valid_email(email) or len(email)>180: return render_template("auth.html",mode="signup",error="Please enter a valid email address.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}",user): return render_template("auth.html",mode="signup",error="Username must be 3–80 characters using letters, numbers, dots, underscores or hyphens.")
        if len(pwd)<8 or len(pwd)>128: return render_template("auth.html",mode="signup",error="Password must be between 8 and 128 characters.")
        try:
            with engine.begin() as c: c.execute(text("INSERT INTO users(full_name,email,username,password_hash) VALUES(:n,:e,:u,:p)"),{"n":name,"e":email.lower(),"u":user,"p":generate_password_hash(pwd)})
            u=one("SELECT id FROM users WHERE username=:u",{"u":user}); session.clear(); session["user_id"]=u["id"]; return redirect(url_for("shop"))
        except Exception: return render_template("auth.html",mode="signup",error="Email or username is already in use.")
    return render_template("auth.html",mode="signup")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=one("SELECT * FROM users WHERE username=:u OR email=:u",{"u":request.form.get("username","").strip()})
        if u and check_password_hash(u["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=u["id"]; return redirect(url_for("shop"))
        return render_template("auth.html",mode="login",error="Invalid username/email or password.")
    return render_template("auth.html",mode="login")

@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin-login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        login_name=request.form.get("username","").strip()
        a=one("SELECT * FROM admins WHERE (username=:u OR email=:u) AND is_active=1",{"u":login_name})
        if a and check_password_hash(a["password_hash"],request.form.get("password","")):
            session.clear();session["admin_id"]=a["id"];session["admin_role"]=a["role"];session["csrf"]=secrets.token_urlsafe(24)
            return redirect(url_for("admin"))
        return render_template("auth.html",mode="admin",error="Invalid admin credentials.")
    return render_template("auth.html",mode="admin")

@app.post("/admin-logout")
@admin_required()
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/wishlist")
@login_required
def wishlist():
    ps=product_query("JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=:u",{"u":session["user_id"]},limit=50)
    return render_template("account.html",tab="wishlist",products=ps,orders=[],user=one("SELECT * FROM users WHERE id=:u",{"u":session["user_id"]}))

@app.post("/wishlist/toggle/<int:pid>")
@login_required
def toggle_wishlist(pid):
    if not one("SELECT id FROM products WHERE id=:p AND status='active'",{"p":pid}): abort(404)
    exists=one("SELECT id FROM wishlist WHERE user_id=:u AND product_id=:p",{"u":session["user_id"],"p":pid})
    with engine.begin() as c:
        if exists:c.execute(text("DELETE FROM wishlist WHERE id=:i AND user_id=:u"),{"i":exists["id"],"u":session["user_id"]})
        else:c.execute(text("INSERT INTO wishlist(user_id,product_id) VALUES(:u,:p)"),{"u":session["user_id"],"p":pid})
    return redirect(url_for("shop"))

@app.post("/cart/add/<int:pid>")
@login_required
def add_cart(pid):
    p=one("SELECT * FROM products WHERE id=:p",{"p":pid})
    qty=parse_int(request.form.get("quantity",1),1,1,100)
    size=(request.form.get("size") or "").strip() or None
    color=(request.form.get("color") or "").strip() or None
    if not p or p.get("status")!="active" or int(p["stock"])<1: abort(400,"Product is unavailable or out of stock.")
    if size and size not in csv_values(p.get("sizes")): abort(400,"Invalid size for this product.")
    if color and color not in csv_values(p.get("colors")): abort(400,"Invalid colour for this product.")
    existing=one("SELECT * FROM cart_items WHERE user_id=:u AND product_id=:p AND COALESCE(size,'')=COALESCE(:s,'') AND COALESCE(color,'')=COALESCE(:c,'')",{"u":session["user_id"],"p":pid,"s":size,"c":color})
    with engine.begin() as c:
        if existing:
            newq=min(p["stock"],existing["quantity"]+qty); c.execute(text("UPDATE cart_items SET quantity=:q WHERE id=:i"),{"q":newq,"i":existing["id"]})
        else:c.execute(text("INSERT INTO cart_items(user_id,product_id,quantity,size,color) VALUES(:u,:p,:q,:s,:c)"),{"u":session["user_id"],"p":pid,"q":min(qty,p["stock"]),"s":size,"c":color})
    return redirect(url_for("cart"))

@app.get("/cart")
@login_required
def cart():
    items=rows("SELECT c.*,p.name,p.brand,p.price,p.original_price,p.image_url,p.stock FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=:u ORDER BY c.id DESC",{"u":session["user_id"]})
    subtotal=sum(float(i["price"])*i["quantity"] for i in items); shipping=0 if subtotal>=5000 or subtotal==0 else 250
    return render_template("cart.html",items=items,subtotal=subtotal,shipping=shipping,total=subtotal+shipping)

@app.post("/cart/update/<int:item_id>")
@login_required
def update_cart(item_id):
    i=one("SELECT c.*,p.stock FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.id=:i AND c.user_id=:u",{"i":item_id,"u":session["user_id"]})
    if not i: abort(404)
    q=parse_int(request.form.get("quantity",1),1,0,100000)
    q=min(q,int(i["stock"]))
    with engine.begin() as c:
        if q:c.execute(text("UPDATE cart_items SET quantity=:q WHERE id=:i AND user_id=:u"),{"q":q,"i":item_id,"u":session["user_id"]})
        else:c.execute(text("DELETE FROM cart_items WHERE id=:i AND user_id=:u"),{"i":item_id,"u":session["user_id"]})
    return redirect(url_for("cart"))

@app.post("/cart/remove/<int:item_id>")
@login_required
def remove_cart(item_id):
    with engine.begin() as c:c.execute(text("DELETE FROM cart_items WHERE id=:i AND user_id=:u"),{"i":item_id,"u":session["user_id"]})
    return redirect(url_for("cart"))

@app.route("/checkout",methods=["GET","POST"])
@login_required
def checkout():
    items=rows("SELECT c.*,p.name,p.price,p.stock,p.status,p.image_url FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=:u",{"u":session["user_id"]})
    if not items:return redirect(url_for("cart"))
    subtotal=sum(float(i["price"])*int(i["quantity"]) for i in items)
    shipping=0 if subtotal>=5000 else 250
    total=subtotal+shipping
    account=os.getenv("PAYMENT_ACCOUNT","03352935407");account_name=os.getenv("PAYMENT_ACCOUNT_NAME","Yours Mart")
    if request.method=="POST":
        fields={k:request.form.get(k,"").strip() for k in ("full_name","phone","province","area","address","city","postal_code","instructions")}
        if not all(fields[k] for k in ("full_name","phone","province","area","address","city")):
            return render_template("checkout.html",items=items,total=total,subtotal=subtotal,discount=0,shipping=shipping,error="Please complete all required delivery details.",payment_account=account,payment_account_name=account_name)
        method=request.form.get("payment_method","").strip().lower()
        if method not in {"cod","easypaisa"}:abort(400,"Unsupported payment method.")
        proof=request.files.get("payment_proof");txref=request.form.get("transaction_ref","").strip()
        if method=="easypaisa" and (not proof or not proof.filename or not txref):
            return render_template("checkout.html",items=items,total=total,subtotal=subtotal,discount=0,shipping=shipping,error="Easypaisa requires the transaction/reference number and payment screenshot.",payment_account=account,payment_account_name=account_name)
        if len(txref)>120:abort(400,"Transaction reference is too long.")
        for i in items:
            if i["status"]!="active" or int(i["stock"])<int(i["quantity"]):
                return render_template("checkout.html",items=items,total=total,subtotal=subtotal,discount=0,shipping=shipping,error=f"{i['name']} is no longer available in the requested quantity.",payment_account=account,payment_account_name=account_name)
        proof_path=save_private_payment_proof(proof) if method=="easypaisa" else None
        payment_status="Pending Verification" if method=="easypaisa" else "Pending"
        order_status="Payment Verification" if method=="easypaisa" else "Confirmed"
        with engine.begin() as c:
            order_number=f"YM-{secrets.token_hex(4).upper()}"
            r=c.execute(text("""INSERT INTO orders(order_number,user_id,subtotal,discount,shipping_fee,total,shipping_address,payment_method,payment_status,status)
                VALUES(:n,:u,:sub,0,:sf,:t,:addr,:m,:ps,:st) RETURNING id"""),{"n":order_number,"u":session["user_id"],"sub":subtotal,"sf":shipping,"t":total,"addr":json.dumps(fields),"m":"Easypaisa" if method=="easypaisa" else "COD","ps":payment_status,"st":order_status})
            oid=r.scalar_one()
            for i in items:
                upd=c.execute(text("UPDATE products SET stock=stock-:q,updated_at=CURRENT_TIMESTAMP WHERE id=:p AND status='active' AND stock>=:q"),{"q":i["quantity"],"p":i["product_id"]})
                if upd.rowcount!=1:raise RuntimeError(f"Stock changed for {i['name']}. Please retry.")
                c.execute(text("INSERT INTO order_items(order_id,product_id,quantity,price,size,color) VALUES(:o,:p,:q,:pr,:s,:c)"),{"o":oid,"p":i["product_id"],"q":i["quantity"],"pr":i["price"],"s":i.get("size"),"c":i.get("color")})
            c.execute(text("INSERT INTO addresses(user_id,full_name,phone,province,area,address,city,postal_code,instructions,is_default) VALUES(:u,:n,:ph,:pv,:ar,:a,:c,:pc,:i,0)"),{"u":session["user_id"],"n":fields["full_name"],"ph":fields["phone"],"pv":fields["province"],"ar":fields["area"],"a":fields["address"],"c":fields["city"],"pc":fields["postal_code"],"i":fields["instructions"]})
            c.execute(text("INSERT INTO payments(order_id,method,amount,transaction_ref,proof_path,status) VALUES(:o,:m,:a,:r,:p,:s)"),{"o":oid,"m":"Easypaisa" if method=="easypaisa" else "COD","a":total,"r":txref or None,"p":proof_path,"s":payment_status})
            c.execute(text("DELETE FROM cart_items WHERE user_id=:u"),{"u":session["user_id"]})
        return redirect(url_for("order_detail",oid=oid))
    return render_template("checkout.html",items=items,total=total,subtotal=subtotal,discount=0,shipping=shipping,payment_account=account,payment_account_name=account_name)

@app.get("/account")
@login_required
def account():
    u=one("SELECT id,full_name,email,username,created_at FROM users WHERE id=:u",{"u":session["user_id"]})
    orders=rows("SELECT * FROM orders WHERE user_id=:u ORDER BY created_at DESC",{"u":session["user_id"]})
    ps=product_query("JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=:u AND p.status='active'",{"u":session["user_id"]},limit=50)
    history=rows("SELECT h.*,p.name,p.image_url FROM tryon_history h JOIN products p ON p.id=h.product_id WHERE h.user_id=:u ORDER BY h.created_at DESC LIMIT 20",{"u":session["user_id"]})
    return render_template("account.html",tab=request.args.get("tab","orders"),products=ps,orders=orders,history=history,user=u)

@app.route("/profile",methods=["GET","POST"])
@login_required
def profile():
    current=one("SELECT id,full_name,email,username FROM users WHERE id=:u",{"u":session["user_id"]})
    if request.method=="POST":
        name=request.form.get("full_name","").strip()
        email=request.form.get("email","").strip().lower()
        username=request.form.get("username","").strip()
        password=request.form.get("password","")
        if not name or len(name)>120 or not valid_email(email) or len(email)>180 or not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}",username):
            return render_template("profile.html",user=current,error="Please enter valid profile details.")
        if password and (len(password)<8 or len(password)>128):
            return render_template("profile.html",user=current,error="Password must be between 8 and 128 characters.")
        try:
            with engine.begin() as c:
                params={"n":name,"e":email,"u":username,"id":session["user_id"]}
                if password:
                    params["p"]=generate_password_hash(password)
                    c.execute(text("UPDATE users SET full_name=:n,email=:e,username=:u,password_hash=:p,updated_at=CURRENT_TIMESTAMP WHERE id=:id"),params)
                else:
                    c.execute(text("UPDATE users SET full_name=:n,email=:e,username=:u,updated_at=CURRENT_TIMESTAMP WHERE id=:id"),params)
        except Exception:
            return render_template("profile.html",user=current,error="Email or username is already in use.")
        current=one("SELECT id,full_name,email,username FROM users WHERE id=:u",{"u":session["user_id"]})
        return render_template("profile.html",user=current,success="Profile updated successfully.",error=None)
    return render_template("profile.html",user=current,success=None,error=None)

@app.get("/orders/<int:oid>")
@login_required
def order_detail(oid):
    o=one("SELECT * FROM orders WHERE id=:o AND user_id=:u",{"o":oid,"u":session["user_id"]})
    if not o:abort(404)
    o["items"]=rows("SELECT oi.*,p.name,p.image_url FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=:o",{"o":oid})
    payment=one("SELECT id,method,amount,transaction_ref,status,rejection_reason,created_at FROM payments WHERE order_id=:o",{"o":oid})
    return render_template("order_detail.html",order=o,payment=payment)

@app.post("/orders/<int:oid>/cancel")
@login_required
def cancel_order(oid):
    o=one("SELECT * FROM orders WHERE id=:o AND user_id=:u",{"o":oid,"u":session["user_id"]})
    if not o:abort(404)
    if o["status"] not in {"Pending Payment","Payment Verification","Confirmed"}:abort(400,"This order can no longer be cancelled online.")
    with engine.begin() as c:
        c.execute(text("UPDATE orders SET status='Cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=:o"),{"o":oid})
        items=c.execute(text("SELECT product_id,quantity FROM order_items WHERE order_id=:o"),{"o":oid}).fetchall()
        for i in items:c.execute(text("UPDATE products SET stock=stock+:q,updated_at=CURRENT_TIMESTAMP WHERE id=:p"),{"q":i[1],"p":i[0]})
    return redirect(url_for("order_detail",oid=oid))

@app.get("/try-on/<slug>")
@login_required
def tryon(slug):
    p=product_dict(one("SELECT * FROM products WHERE slug=:s",{"s":slug}))
    if not p: abort(404)
    return render_template("tryon.html",product=p)

@app.post("/api/tryon/<int:pid>")
@login_required
def tryon_start(pid):
    p=one("SELECT * FROM products WHERE id=:p",{"p":pid})
    f=request.files.get("photo")
    if not p or not f:return jsonify(error="Product and photo are required."),400
    if f.mimetype not in {"image/jpeg","image/png","image/webp"}:return jsonify(error="Use JPG, PNG, or WebP."),400
    raw=f.read()
    if not raw or len(raw)>8*1024*1024:return jsonify(error="Image must be between 1 byte and 8MB."),400
    try:
        img=Image.open(BytesIO(raw))
        img.verify()
    except (UnidentifiedImageError, OSError):
        return jsonify(error="The uploaded file is not a valid image."),400
    try:
        result=generate_virtual_tryon((raw,f.mimetype),p["image_url"])
    except TryOnError:
        return jsonify(error="AI Try-On is temporarily unavailable. Please try again later."),503
    if result.get("mode")=="unavailable":
        return jsonify(error=result.get("message","AI Try-On is not configured yet.")),503
    with engine.begin() as c:
        r=c.execute(text("INSERT INTO tryon_history(user_id,product_id,job_id,status) VALUES(:u,:p,:j,'processing') RETURNING id"),{"u":session["user_id"],"p":pid,"j":result["job_id"]})
        hid=r.scalar_one()
    return jsonify(mode="live",status="processing",history_id=hid,job_id=result["job_id"])

@app.get("/api/tryon/status/<job_id>")
@login_required
def tryon_status(job_id):
    owned=one("SELECT id FROM tryon_history WHERE job_id=:j AND user_id=:u",{"j":job_id,"u":session["user_id"]})
    if not owned:return jsonify(error="Try-on job not found."),404
    try:r=get_virtual_tryon_status(job_id)
    except TryOnError as e:return jsonify(status="failed",error="The AI provider is temporarily unavailable."),502
    if r.get("status")=="completed":
        with engine.begin() as c:c.execute(text("UPDATE tryon_history SET status='completed',result_url=:r WHERE job_id=:j AND user_id=:u"),{"r":r.get("output"),"j":job_id,"u":session["user_id"]})
    elif r.get("status")=="failed":
        with engine.begin() as c:c.execute(text("UPDATE tryon_history SET status='failed' WHERE job_id=:j AND user_id=:u"),{"j":job_id,"u":session["user_id"]})
    return jsonify(r)

@app.post("/api/assistant")
def assistant():
    query=request.json.get("message","").strip() if request.is_json else request.form.get("message","").strip()
    if not query:return jsonify(error="Ask me about products, outfits, budgets, colours or sizes."),400
    words=re.findall(r"[a-z0-9]+",query.lower())
    stopwords={"a","an","and","for","in","is","it","me","my","of","on","or","the","to","under","with","show","find","want","need","please","outfit","look"}
    keywords=[w for w in words if len(w)>2 and w not in stopwords]
    budget=None
    m=re.search(r"(?:under|below|less than)\s*(?:rs\.?\s*)?([0-9,]+)",query.lower())
    if m: budget=float(m.group(1).replace(",",""))
    params={}
    clauses=[]
    for idx,w in enumerate(keywords):
        clauses.append(f"(LOWER(name) LIKE :w{idx} OR LOWER(brand) LIKE :w{idx} OR LOWER(category) LIKE :w{idx} OR LOWER(tags) LIKE :w{idx} OR LOWER(colors) LIKE :w{idx})")
        params[f"w{idx}"]=f"%{w}%"
    sql="SELECT * FROM products"
    if clauses: sql+=" WHERE ("+" OR ".join(clauses)+")"
    if budget is not None: sql+=(" AND " if clauses else " WHERE ")+"price<=:b"; params["b"]=budget
    sql+=" ORDER BY rating DESC LIMIT 20"
    candidates=[product_dict(x) for x in rows(sql,params)]
    def relevance(p):
        hay=" ".join([str(p.get("name") or ""),str(p.get("brand") or ""),str(p.get("category") or ""),str(p.get("tags") or ""),str(p.get("colors") or "")]).lower()
        hits=sum(1 for w in keywords if w in hay)
        return (hits,float(p.get("rating") or 0))
    candidates.sort(key=relevance,reverse=True)
    matches=candidates[:6]
    if not matches: matches=product_query("WHERE p.status='active'",limit=6)
    if not matches:
        return jsonify(reply="I couldn't find any active products right now. Please try again later.",products=[])
    total=sum(float(x["price"]) for x in matches[:3])
    # Optional LLM layer: the model only receives live catalog matches, so it cannot invent unavailable products.
    ak=os.getenv("AI_ASSISTANT_API_KEY"); au=os.getenv("AI_ASSISTANT_API_URL"); am=os.getenv("AI_ASSISTANT_MODEL")
    if ak and au and am:
        try:
            import requests
            catalog=[{"name":x["name"],"brand":x["brand"],"category":x["category"],"price":float(x["price"]),"colors":x["colors"],"sizes":x["sizes"],"stock":x["stock"],"rating":float(x["rating"])} for x in matches[:6]]
            payload={"model":am,"messages":[{"role":"system","content":"You are Yours AI, a concise fashion shopping assistant. Recommend only products present in the supplied catalog. Mention price and availability when useful. Never invent a product."},{"role":"user","content":json.dumps({"question":query,"catalog":catalog})}],"temperature":0.4}
            rr=requests.post(au,headers={"Authorization":f"Bearer {ak}","Content-Type":"application/json"},json=payload,timeout=20)
            if rr.ok:
                reply=rr.json()["choices"][0]["message"]["content"]
                return jsonify(reply=reply,products=matches[:6])
        except Exception:
            pass
    return jsonify(reply=f"I found {len(matches)} catalog matches. I’d start with {matches[0]['name']} and build around its {matches[0]['colors'][0] if matches[0]['colors'] else 'neutral'} palette. {('The first three total about Rs. '+format(total,',.0f')+'.') if matches else ''}",products=matches[:6])

ADMIN_PERMISSIONS={"manage_products","manage_orders","manage_inventory","manage_customers","manage_payments","view_reports","manage_settings"}

@app.get("/admin")
@admin_required()
def admin():
    stats={"sales":float(one("SELECT COALESCE(SUM(total),0) n FROM orders WHERE status NOT IN ('Cancelled','Refunded') AND (payment_method='COD' OR payment_status IN ('Verified','Paid'))")["n"]),
           "orders":int(one("SELECT COUNT(*) n FROM orders")["n"]),"pending":int(one("SELECT COUNT(*) n FROM orders WHERE status IN ('Pending Payment','Payment Verification','Confirmed','Processing','Packed')")["n"]),
           "shipped":int(one("SELECT COUNT(*) n FROM orders WHERE status IN ('Shipped','Out for Delivery')")["n"]),"delivered":int(one("SELECT COUNT(*) n FROM orders WHERE status='Delivered'")["n"]),
           "customers":int(one("SELECT COUNT(*) n FROM users WHERE role='customer'")["n"]),"products":int(one("SELECT COUNT(*) n FROM products WHERE status!='archived'")["n"]),
           "low":int(one("SELECT COUNT(*) n FROM products WHERE stock<=min_stock AND status='active'")["n"]),"out":int(one("SELECT COUNT(*) n FROM products WHERE stock=0 AND status='active'")["n"])}
    orders=rows("SELECT o.*,u.full_name,u.email FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created_at DESC LIMIT 30")
    products=product_query("WHERE p.status!='archived'",limit=100);cats=rows("SELECT * FROM categories ORDER BY name")
    payments=rows("SELECT p.*,o.order_number,u.full_name FROM payments p JOIN orders o ON o.id=p.order_id JOIN users u ON u.id=o.user_id ORDER BY p.created_at DESC LIMIT 30")
    chart_status=rows("SELECT status,COUNT(*) n FROM orders GROUP BY status")
    chart_categories=rows("SELECT p.category,SUM(oi.quantity*oi.price) sales FROM order_items oi JOIN products p ON p.id=oi.product_id GROUP BY p.category ORDER BY sales DESC LIMIT 8")
    return render_template("admin.html",stats=stats,orders=orders,products=products,categories=cats,payments=payments,chart_status=chart_status,chart_categories=chart_categories,admin_role=session.get("admin_role"))

@app.post("/admin/product")
@admin_required("manage_products")
def admin_product():
    f=request.form;pid=f.get("id");name=f.get("name","").strip();brand=f.get("brand","").strip();cat=f.get("category","").strip()
    price=parse_money(f.get("price"));orig=parse_money(f.get("original_price",price));stock=parse_int(f.get("stock"),0,0,1000000);min_stock=parse_int(f.get("min_stock"),5,0,100000)
    status=f.get("status","active");featured=1 if f.get("featured") else 0
    sizes=f.get("sizes","One Size").strip() or "One Size";colors=f.get("colors","Black").strip() or "Black";tags=f.get("tags","casual").strip() or "casual";image=f.get("image_url","").strip()
    if status not in {"active","draft","archived"} or not name or len(name)>180 or len(brand)>120 or len(cat)>120 or price<=0 or orig<price:abort(400,"Invalid product details.")
    if not image:image="https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85"
    if urlparse(image).scheme not in {"http","https"}:abort(400,"Product image must use HTTP(S).")
    slug=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-") or f"product-{secrets.token_hex(4)}"
    existing=one("SELECT id FROM products WHERE slug=:s",{"s":slug})
    if existing and (not pid or int(existing["id"])!=int(pid)):slug=f"{slug}-{secrets.token_hex(3)}"
    data={"name":name,"brand":brand,"cat":cat,"price":price,"orig":orig,"disc":round((1-price/orig)*100,1),"stock":stock,"min_stock":min_stock,"sizes":sizes,"colors":colors,"tags":tags,"image":image,"slug":slug,"status":status,"featured":featured,"desc":f"{name} by {brand}."}
    with engine.begin() as c:
        if pid:c.execute(text("""UPDATE products SET name=:name,slug=:slug,brand=:brand,category=:cat,description=:desc,price=:price,original_price=:orig,discount=:disc,stock=:stock,min_stock=:min_stock,sizes=:sizes,colors=:colors,tags=:tags,image_url=:image,status=:status,featured=:featured,updated_at=CURRENT_TIMESTAMP WHERE id=:id"""),{**data,"id":int(pid)})
        else:c.execute(text("""INSERT INTO products(name,slug,brand,category,description,price,original_price,discount,stock,min_stock,sizes,colors,tags,image_url,status,featured) VALUES(:name,:slug,:brand,:cat,:desc,:price,:orig,:disc,:stock,:min_stock,:sizes,:colors,:tags,:image,:status,:featured)"""),data)
    admin_audit("product_saved","product",pid or "new",name);return redirect(url_for("admin"))

@app.post("/admin/product/archive/<int:pid>")
@admin_required("manage_products")
def admin_product_archive(pid):
    if not one("SELECT id FROM products WHERE id=:p",{"p":pid}):abort(404)
    exec_sql("UPDATE products SET status='archived',stock=0,updated_at=CURRENT_TIMESTAMP WHERE id=:p",{"p":pid});admin_audit("product_archived","product",pid);return redirect(url_for("admin"))

@app.post("/admin/inventory/<int:pid>")
@admin_required("manage_inventory")
def admin_inventory(pid):
    change=parse_int(request.form.get("change"),0,-1000000,1000000);reason=request.form.get("reason","Manual adjustment").strip()[:160]
    p=one("SELECT stock FROM products WHERE id=:p",{"p":pid})
    if not p or change==0:abort(400)
    new=max(0,int(p["stock"])+change)
    with engine.begin() as c:
        c.execute(text("UPDATE products SET stock=:s,updated_at=CURRENT_TIMESTAMP WHERE id=:p"),{"s":new,"p":pid})
        c.execute(text("INSERT INTO inventory_transactions(product_id,admin_id,change_qty,stock_after,reason) VALUES(:p,:a,:q,:s,:r)"),{"p":pid,"a":session["admin_id"],"q":change,"s":new,"r":reason})
    admin_audit("inventory_adjusted","product",pid,f"{change:+d} => {new}");return redirect(url_for("admin"))

@app.post("/admin/order/<int:oid>")
@admin_required("manage_orders")
def admin_order(oid):
    status=request.form.get("status","").strip()
    allowed={"Pending Payment","Payment Verification","Confirmed","Processing","Packed","Shipped","Out for Delivery","Delivered","Cancelled","Returned","Refunded"}
    if status not in allowed:abort(400)
    o=one("SELECT * FROM orders WHERE id=:o",{"o":oid})
    if not o:abort(404)
    if status=="Delivered" and o["payment_method"]=="Easypaisa" and o["payment_status"]!="Verified":abort(400,"Payment must be verified before delivery.")
    exec_sql("UPDATE orders SET status=:s,updated_at=CURRENT_TIMESTAMP WHERE id=:o",{"s":status,"o":oid});admin_audit("order_status_changed","order",oid,status);return redirect(url_for("admin"))

@app.post("/admin/payment/<int:payment_id>")
@admin_required("manage_payments")
def admin_payment(payment_id):
    status=request.form.get("status","").strip();reason=request.form.get("reason","").strip()[:500]
    if status not in {"Verified","Rejected"}:abort(400)
    p=one("SELECT * FROM payments WHERE id=:i",{"i":payment_id})
    if not p:abort(404)
    with engine.begin() as c:
        c.execute(text("UPDATE payments SET status=:s,rejection_reason=:r,verified_by=:v,verified_at=CURRENT_TIMESTAMP WHERE id=:i"),{"s":status,"r":reason or None,"v":session["admin_id"],"i":payment_id})
        c.execute(text("UPDATE orders SET payment_status=:ps,status=:os,updated_at=CURRENT_TIMESTAMP WHERE id=:o"),{"ps":status,"os":"Confirmed" if status=="Verified" else "Payment Verification","o":p["order_id"]})
    admin_audit("payment_reviewed","payment",payment_id,status);return redirect(url_for("admin"))

@app.get("/admin/payment-proof/<int:payment_id>")
@admin_required("manage_payments")
def admin_payment_proof(payment_id):
    p=one("SELECT proof_path FROM payments WHERE id=:i",{"i":payment_id})
    if not p or not p["proof_path"]:abort(404)
    stored=p["proof_path"]
    if stored.startswith("cloudinary:"):
        try:
            meta=json.loads(stored.split(":",1)[1])
            cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),api_key=os.getenv("CLOUDINARY_API_KEY"),api_secret=os.getenv("CLOUDINARY_API_SECRET"),secure=True)
            url=cloudinary.CloudinaryImage(meta["public_id"]).build_url(type="authenticated",sign_url=True,secure=True)
            return redirect(url)
        except Exception:abort(404)
    path=os.path.abspath(stored)
    if not path.startswith(os.path.abspath(private_payment_dir())):abort(403)
    if not os.path.exists(path):abort(404)
    return send_file(path)

@app.get("/admin/customers")
@admin_required("manage_customers")
def admin_customers():
    users=rows("SELECT id,full_name,email,username,is_active,created_at FROM users WHERE role='customer' ORDER BY created_at DESC")
    return render_template("admin_customers.html",users=users)

@app.post("/admin/customer/<int:uid>/toggle")
@admin_required("manage_customers")
def admin_customer_toggle(uid):
    u=one("SELECT * FROM users WHERE id=:u AND role='customer'",{"u":uid})
    if not u:abort(404)
    exec_sql("UPDATE users SET is_active=:a,updated_at=CURRENT_TIMESTAMP WHERE id=:u",{"a":0 if u["is_active"] else 1,"u":uid});admin_audit("customer_status_changed","user",uid);return redirect(url_for("admin_customers"))

@app.get("/superadmin")
@admin_required(superadmin=True)
def superadmin():
    admins=rows("SELECT id,username,email,full_name,role,is_active,created_at FROM admins ORDER BY created_at DESC")
    logs=rows("SELECT l.*,a.username FROM audit_logs l LEFT JOIN admins a ON a.id=l.admin_id ORDER BY l.created_at DESC LIMIT 50")
    return render_template("superadmin.html",admins=admins,logs=logs,permissions=sorted(ADMIN_PERMISSIONS))

@app.post("/superadmin/admin")
@admin_required(superadmin=True)
def superadmin_create_admin():
    username=request.form.get("username","").strip();email=request.form.get("email","").strip().lower();name=request.form.get("full_name","").strip();pwd=request.form.get("password","");role=request.form.get("role","admin")
    if role not in {"admin","superadmin"} or not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}",username) or not valid_email(email) or len(pwd)<12:abort(400,"Use valid account details and a password of at least 12 characters.")
    try:
        with engine.begin() as c:
            c.execute(text("INSERT INTO admins(username,email,full_name,password_hash,role) VALUES(:u,:e,:n,:p,:r)"),{"u":username,"e":email,"n":name[:120],"p":generate_password_hash(pwd),"r":role})
            aid=c.execute(text("SELECT id FROM admins WHERE username=:u"),{"u":username}).scalar()
            for perm in ADMIN_PERMISSIONS:c.execute(text("INSERT INTO admin_permissions(admin_id,permission) VALUES(:a,:p)"),{"a":aid,"p":perm})
    except Exception:abort(400,"Username or email is already in use.")
    admin_audit("admin_created","admin",aid,username);return redirect(url_for("superadmin"))

@app.post("/superadmin/admin/<int:aid>/toggle")
@admin_required(superadmin=True)
def superadmin_toggle(aid):
    if aid==session["admin_id"]:abort(400,"You cannot disable your own account.")
    a=one("SELECT * FROM admins WHERE id=:a",{"a":aid})
    if not a:abort(404)
    exec_sql("UPDATE admins SET is_active=:v,updated_at=CURRENT_TIMESTAMP WHERE id=:a",{"v":0 if a["is_active"] else 1,"a":aid});admin_audit("admin_status_changed","admin",aid);return redirect(url_for("superadmin"))

@app.post("/superadmin/admin/<int:aid>/permissions")
@admin_required(superadmin=True)
def superadmin_permissions(aid):
    if not one("SELECT id FROM admins WHERE id=:a",{"a":aid}):abort(404)
    selected=set(request.form.getlist("permissions"))
    with engine.begin() as c:
        c.execute(text("DELETE FROM admin_permissions WHERE admin_id=:a"),{"a":aid})
        for perm in selected & ADMIN_PERMISSIONS:c.execute(text("INSERT INTO admin_permissions(admin_id,permission) VALUES(:a,:p)"),{"a":aid,"p":perm})
    admin_audit("admin_permissions_updated","admin",aid,",".join(sorted(selected)));return redirect(url_for("superadmin"))
def private_payment_dir():
    path=os.path.join(BASE_DIR,"instance","private_payments")
    os.makedirs(path,exist_ok=True)
    return path

def save_private_payment_proof(file_obj):
    raw=file_obj.read()
    if not raw or len(raw)>8*1024*1024:abort(400,"Payment proof must be a valid image under 8MB.")
    try:
        img=Image.open(BytesIO(raw))
        if img.format not in {"JPEG","PNG","WEBP"}:raise ValueError
        img.verify()
    except Exception:abort(400,"Payment proof must be JPG, PNG or WebP.")
    # Cloudinary authenticated assets are appropriate for production/serverless because they
    # require signed delivery URLs; local disk remains the development fallback.
    if all(os.getenv(k) for k in ("CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET")):
        cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),api_key=os.getenv("CLOUDINARY_API_KEY"),api_secret=os.getenv("CLOUDINARY_API_SECRET"),secure=True)
        result=cloudinary.uploader.upload(BytesIO(raw),folder="yours-mart/payment-proofs",type="authenticated",resource_type="image")
        return "cloudinary:"+json.dumps({"public_id":result["public_id"],"format":result.get("format","jpg")})
    path=os.path.join(private_payment_dir(),f"{uuid.uuid4().hex}.img")
    with open(path,"wb") as fh:fh.write(raw)
    return path

@app.get("/health")
def health():
    try:
        one("SELECT 1")
        return jsonify(status="ok",database="ok",app="yours-mart")
    except Exception:
        return jsonify(status="degraded",database="unavailable",app="yours-mart"),503

@app.errorhandler(400)
def bad_request(e): return render_template("error.html",code=400,message=getattr(e,"description","The request could not be processed.") or "The request could not be processed."),400

@app.errorhandler(401)
def unauthorized(e): return render_template("error.html",code=401,message="You need to sign in to continue."),401

@app.errorhandler(403)
def forbidden(e): return render_template("error.html",code=403,message=getattr(e,"description","You do not have permission to access this resource.") or "You do not have permission to access this resource."),403

@app.errorhandler(404)
def not_found(e): return render_template("error.html",code=404,message="That page does not exist."),404

@app.errorhandler(405)
def method_not_allowed(e): return render_template("error.html",code=405,message="That action is not available here."),405

@app.errorhandler(500)
def server_error(e): return render_template("error.html",code=500,message="Something went wrong. Please try again."),500

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
