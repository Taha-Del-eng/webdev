import os, json, math, re, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from dotenv import load_dotenv
from .services.ai_tryon import generate_virtual_tryon, get_virtual_tryon_status, TryOnError
from .services.recommendations import recommend
from .services.storage import upload_file

load_dotenv()
BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///yours_mart.db")
if DATABASE_URL.startswith("postgres://"): DATABASE_URL=DATABASE_URL.replace("postgres://","postgresql+psycopg://",1)
elif DATABASE_URL.startswith("postgresql://"): DATABASE_URL=DATABASE_URL.replace("postgresql://","postgresql+psycopg://",1)
engine=create_engine(DATABASE_URL, pool_pre_ping=True, future=True, connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {})
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
    """CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, name VARCHAR(180) NOT NULL, slug VARCHAR(220) UNIQUE NOT NULL, brand VARCHAR(120), category VARCHAR(120) NOT NULL, description TEXT, price NUMERIC(12,2) NOT NULL, original_price NUMERIC(12,2), discount NUMERIC(5,2) DEFAULT 0, stock INTEGER DEFAULT 0, sizes TEXT, colors TEXT, rating NUMERIC(3,2) DEFAULT 0, review_count INTEGER DEFAULT 0, tags TEXT, image_url TEXT NOT NULL, additional_images TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS cart_items(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, size VARCHAR(30), color VARCHAR(50), UNIQUE(user_id,product_id,size,color))""",
    """CREATE TABLE IF NOT EXISTS wishlist(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, UNIQUE(user_id,product_id))""",
    """CREATE TABLE IF NOT EXISTS addresses(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL, full_name VARCHAR(120), phone VARCHAR(40), address TEXT, city VARCHAR(80), postal_code VARCHAR(30), instructions TEXT)""",
    """CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL, total NUMERIC(12,2) NOT NULL, shipping_address TEXT NOT NULL, payment_method VARCHAR(40) DEFAULT 'COD', payment_status VARCHAR(40) DEFAULT 'Pending', status VARCHAR(40) DEFAULT 'Pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, price NUMERIC(12,2) NOT NULL, size VARCHAR(30), color VARCHAR(50))""",
    """CREATE TABLE IF NOT EXISTS tryon_history(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, job_id VARCHAR(255), status VARCHAR(40), result_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS categories_meta(id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY, name VARCHAR(120) UNIQUE NOT NULL)"""
    ]
    with engine.begin() as c:
        for q in ddl:
            try: c.execute(text(q))
            except Exception:
                if "GENERATED ALWAYS AS IDENTITY" in q:
                    c.execute(text(q.replace("INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY","INTEGER PRIMARY KEY AUTOINCREMENT")))
                else: raise
        count=c.execute(text("SELECT COUNT(*) FROM products")).scalar()
        if not count:
            for name in CATEGORIES: c.execute(text("INSERT INTO categories(name) VALUES(:n) ON CONFLICT DO NOTHING"),{"n":name})
            for p in SEED:
                slug=re.sub(r"[^a-z0-9]+","-",p[0].lower()).strip("-")
                c.execute(text("""INSERT INTO products(name,slug,brand,category,description,price,original_price,discount,stock,sizes,colors,rating,review_count,tags,image_url,additional_images)
                VALUES(:name,:slug,:brand,:cat,:desc,:price,:orig,:disc,:stock,:sizes,:colors,:rating,:reviews,:tags,:image,:additional)"""),
                dict(name=p[0],slug=slug,brand=p[1],cat=p[2],desc=f"{p[0]} by {p[1]}. Curated for everyday style with premium materials and an easy-to-wear silhouette.",price=float(p[3]),orig=float(p[4]),disc=round((1-float(p[3])/float(p[4]))*100,1),stock=p[5],sizes=p[6],colors=p[7],rating=float(p[8]),reviews=p[9],tags=p[10],image=p[11],additional=json.dumps([p[11]])))
        admin=os.getenv("ADMIN_USERNAME")
        if admin and not c.execute(text("SELECT id FROM users WHERE username=:u"),{"u":admin}).first():
            pass

try: init_db()
except Exception as exc: print("Database initialization deferred:", exc)

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
        if not session.get("user_id"): return redirect(url_for("login"))
        return f(*a,**k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return f(*a,**k)
    return w

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
    products=product_query(limit=8)
    return render_template("landing.html", trending=products[:4], new_arrivals=products[:4], best_sellers=sorted(products,key=lambda x:-float(x["rating"]))[:4], categories=rows("SELECT * FROM categories ORDER BY name"), recommended=products[4:8])

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
    p=product_dict(one("SELECT * FROM products WHERE slug=:s",{"s":slug}))
    if not p: abort(404)
    allp=product_query(limit=40)
    return render_template("product.html",product=p,similar=recommend(allp,p,4),complete=recommend(allp,{"id":-1,"category":p["category"],"price":p["price"],"tags":",".join(p["tags"])},4))

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
        if request.form.get("username")==os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD_HASH") and check_password_hash(os.getenv("ADMIN_PASSWORD_HASH"),request.form.get("password","")):
            session.clear(); session["admin"]=True; return redirect(url_for("admin"))
        return render_template("auth.html",mode="admin",error="Invalid admin credentials.")
    return render_template("auth.html",mode="admin")

@app.get("/wishlist")
@login_required
def wishlist():
    ps=product_query("JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=:u",{"u":session["user_id"]},limit=50)
    return render_template("account.html",tab="wishlist",products=ps,orders=[],user=one("SELECT * FROM users WHERE id=:u",{"u":session["user_id"]}))

@app.post("/wishlist/toggle/<int:pid>")
@login_required
def toggle_wishlist(pid):
    exists=one("SELECT id FROM wishlist WHERE user_id=:u AND product_id=:p",{"u":session["user_id"],"p":pid})
    with engine.begin() as c:
        if exists:c.execute(text("DELETE FROM wishlist WHERE id=:i"),{"i":exists["id"]})
        else:c.execute(text("INSERT INTO wishlist(user_id,product_id) VALUES(:u,:p)"),{"u":session["user_id"],"p":pid})
    return redirect(url_for("shop"))

@app.post("/cart/add/<int:pid>")
@login_required
def add_cart(pid):
    p=one("SELECT * FROM products WHERE id=:p",{"p":pid})
    qty=parse_int(request.form.get("quantity",1),1,1,100)
    size=(request.form.get("size") or "").strip() or None
    color=(request.form.get("color") or "").strip() or None
    if not p or p["stock"]<1: abort(400,"Product is out of stock.")
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
    if i:
        q=max(0,min(int(request.form.get("quantity",1)),i["stock"]))
        with engine.begin() as c:
            if q:c.execute(text("UPDATE cart_items SET quantity=:q WHERE id=:i"),{"q":q,"i":item_id})
            else:c.execute(text("DELETE FROM cart_items WHERE id=:i"),{"i":item_id})
    return redirect(url_for("cart"))

@app.post("/cart/remove/<int:item_id>")
@login_required
def remove_cart(item_id):
    with engine.begin() as c:c.execute(text("DELETE FROM cart_items WHERE id=:i AND user_id=:u"),{"i":item_id,"u":session["user_id"]})
    return redirect(url_for("cart"))

@app.route("/checkout",methods=["GET","POST"])
@login_required
def checkout():
    items=rows("SELECT c.*,p.name,p.price,p.stock FROM cart_items c JOIN products p ON p.id=c.product_id WHERE c.user_id=:u",{"u":session["user_id"]})
    if not items:return redirect(url_for("cart"))
    subtotal=sum(float(i["price"])*i["quantity"] for i in items); shipping=0 if subtotal>=5000 else 250; total=subtotal+shipping
    if request.method=="POST":
        fields={k:request.form.get(k,"").strip() for k in ("full_name","phone","address","city","postal_code","instructions")}
        if not all(fields[k] for k in ("full_name","phone","address","city","postal_code")):
            return render_template("checkout.html",items=items,total=total,subtotal=subtotal,shipping=shipping,error="Please complete all required delivery fields.")
        if any(len(fields[k])>500 for k in ("address","instructions")) or len(fields["full_name"])>120 or len(fields["city"])>80 or len(fields["postal_code"])>30 or len(fields["phone"])>40:
            return render_template("checkout.html",items=items,total=total,subtotal=subtotal,shipping=shipping,error="One or more delivery fields are too long.")
        with engine.begin() as c:
            for i in items:
                updated=c.execute(text("UPDATE products SET stock=stock-:q,updated_at=CURRENT_TIMESTAMP WHERE id=:p AND stock>=:q RETURNING id"),{"q":i["quantity"],"p":i["product_id"]})
                if not updated.first():
                    abort(409,f"Not enough stock for {i['name']}.")
            r=c.execute(text("INSERT INTO orders(user_id,total,shipping_address,payment_method,payment_status,status) VALUES(:u,:t,:a,'COD','Pending','Pending') RETURNING id"),{"u":session["user_id"],"t=total,"a":json.dumps(fields)})
            oid=r.scalar_one()
            c.execute(text("INSERT INTO addresses(user_id,full_name,phone,address,city,postal_code,instructions) VALUES(:u,:n,:ph,:a,:c,:pc,:i)"),{"u":session["user_id"],"n":fields["full_name"],"ph":fields["phone"],"a":fields["address"],"c":fields["city"],"pc":fields["postal_code"],"i":fields["instructions"]})
            for i in items:
                c.execute(text("INSERT INTO order_items(order_id,product_id,quantity,price,size,color) VALUES(:o,:p,:q,:pr,:s,:c)"),{"o":oid,"p":i["product_id"],"q":i["quantity"],"pr":i["price"],"s":i.get("size"),"c":i.get("color")})
            c.execute(text("DELETE FROM cart_items WHERE user_id=:u"),{"u":session["user_id"]})
        return render_template("checkout.html",items=[],total=0,subtotal=0,shipping=0,success=f"Order #{oid} placed successfully. Cash on Delivery selected.")
    return render_template("checkout.html",items=items,total=total,subtotal=subtotal,shipping=shipping)

@app.get("/account")
@login_required
def account():
    u=one("SELECT * FROM users WHERE id=:u",{"u":session["user_id"]})
    orders=rows("SELECT * FROM orders WHERE user_id=:u ORDER BY created_at DESC",{"u":session["user_id"]})
    ps=product_query("JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=:u",{"u":session["user_id"]},limit=50)
    history=rows("SELECT h.*,p.name,p.image_url FROM tryon_history h JOIN products p ON p.id=h.product_id WHERE h.user_id=:u ORDER BY h.created_at DESC LIMIT 20",{"u":session["user_id"]})
    return render_template("account.html",tab=request.args.get("tab","orders"),products=ps,orders=orders,history=history,user=u)

@app.get("/orders/<int:oid>")
@login_required
def order_detail(oid):
    o=one("SELECT * FROM orders WHERE id=:o AND user_id=:u",{"o":oid,"u":session["user_id"]})
    if not o: abort(404)
    o["items"]=rows("SELECT oi.*,p.name,p.image_url FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=:o",{"o":oid})
    return render_template("account.html",tab="orders",products=[],orders=[o],user=one("SELECT * FROM users WHERE id=:u",{"u":session["user_id"]}))

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
    result=generate_virtual_tryon((raw,f.mimetype),p["image_url"])
    with engine.begin() as c:
        if result["mode"]=="mock":
            c.execute(text("INSERT INTO tryon_history(user_id,product_id,status,result_url) VALUES(:u,:p,'mock',:r)"),{"u":session["user_id"],"p":pid,"r":p["image_url"]})
            return jsonify(mode="mock",status="mock",output=p["image_url"],message="Live AI is not configured; showing a safe demo result.")
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
    if not matches: matches=product_query(limit=6)
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

@app.get("/admin")
@admin_required
def admin():
    stats={
      "sales":float(one("SELECT COALESCE(SUM(total),0) n FROM orders WHERE status!='Cancelled'")["n"]),
      "orders":int(one("SELECT COUNT(*) n FROM orders")["n"]),
      "customers":int(one("SELECT COUNT(*) n FROM users")["n"]),
      "products":int(one("SELECT COUNT(*) n FROM products")["n"]),
      "low":int(one("SELECT COUNT(*) n FROM products WHERE stock<=5")["n"]),
      "pending":int(one("SELECT COUNT(*) n FROM orders WHERE status IN ('Pending','Confirmed')")["n"])
    }
    orders=rows("SELECT o.*,u.full_name,u.email FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created_at DESC LIMIT 20")
    products=product_query(limit=100)
    cats=rows("SELECT * FROM categories ORDER BY name")
    chart_status=rows("SELECT status,COUNT(*) n FROM orders GROUP BY status")
    chart_categories=rows("SELECT category,SUM(oi.quantity*oi.price) sales FROM order_items oi JOIN products p ON p.id=oi.product_id GROUP BY category ORDER BY sales DESC LIMIT 8")
    return render_template("admin.html",stats=stats,orders=orders,products=products,categories=cats,chart_status=chart_status,chart_categories=chart_categories)

@app.post("/admin/product")
@admin_required
def admin_product():
    f=request.form
    pid=f.get("id"); name=f.get("name","").strip(); brand=f.get("brand","").strip(); cat=f.get("category","").strip()
    price=parse_money(f.get("price",0)); orig=parse_money(f.get("original_price",price)); stock=parse_int(f.get("stock",0),0,0,1000000)
    sizes=f.get("sizes","S,M,L,XL").strip() or "One Size"; colors=f.get("colors","Black").strip() or "Black"; tags=f.get("tags","casual").strip() or "casual"; image=f.get("image_url","").strip()
    if not name or len(name)>180 or len(brand)>120 or len(cat)>120: abort(400,"Invalid product details.")
    if price<=0 or orig<price: abort(400,"Original price must be greater than or equal to sale price.")
    if not image and request.files.get("image") and request.files["image"].filename:
        try:image=upload_file(request.files["image"])
        except Exception: image=""
    if not image:image="https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85"
    slug=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-")
    data={"name":name,"brand":brand,"cat":cat,"price":price,"orig":orig,"disc":round((1-price/orig)*100,1) if orig else 0,"stock":stock,"sizes":sizes,"colors":colors,"tags":tags,"image":image,"slug":slug,"desc":f"{name} by {brand}."}
    with engine.begin() as c:
        if pid:c.execute(text("""UPDATE products SET name=:name,slug=:slug,brand=:brand,category=:cat,description=:desc,price=:price,original_price=:orig,discount=:disc,stock=:stock,sizes=:sizes,colors=:colors,tags=:tags,image_url=:image,updated_at=CURRENT_TIMESTAMP WHERE id=:id"""),{**data,"id":int(pid)})
        else:c.execute(text("""INSERT INTO products(name,slug,brand,category,description,price,original_price,discount,stock,sizes,colors,tags,image_url) VALUES(:name,:slug,:brand,:cat,:desc,:price,:orig,:disc,:stock,:sizes,:colors,:tags,:image)"""),data)
    return redirect(url_for("admin"))

@app.post("/admin/product/delete/<int:pid>")
@admin_required
def admin_product_delete(pid):
    refs=one("SELECT (SELECT COUNT(*) FROM order_items WHERE product_id=:p) orders,(SELECT COUNT(*) FROM cart_items WHERE product_id=:p) carts,(SELECT COUNT(*) FROM wishlist WHERE product_id=:p) wishes",{"p":pid})
    if not refs: abort(404)
    if int(refs["orders"]) or int(refs["carts"]) or int(refs["wishes"]):
        flash("This product cannot be deleted because it is referenced by an order, cart, or wishlist. Set stock to 0 instead.")
        return redirect(url_for("admin"))
    with engine.begin() as c:c.execute(text("DELETE FROM products WHERE id=:p"),{"p":pid})
    return redirect(url_for("admin"))

@app.post("/admin/order/<int:oid>")
@admin_required
def admin_order(oid):
    status=request.form.get("status","Pending")
    if status not in {"Pending","Confirmed","Processing","Shipped","Delivered","Cancelled"}:abort(400)
    with engine.begin() as c:c.execute(text("UPDATE orders SET status=:s,payment_status=:ps WHERE id=:o"),{"s":status,"ps":"Paid" if status=="Delivered" else "Pending","o":oid})
    return redirect(url_for("admin"))

@app.post("/admin/category")
@admin_required
def admin_category():
    name=request.form.get("name","").strip()
    if name:
        with engine.begin() as c:c.execute(text("INSERT INTO categories(name) VALUES(:n) ON CONFLICT DO NOTHING"),{"n":name})
    return redirect(url_for("admin"))

@app.get("/health")
def health():
    try:
        one("SELECT 1")
        return jsonify(status="ok",database="ok",app="yours-mart")
    except Exception:
        return jsonify(status="degraded",database="unavailable",app="yours-mart"),503

@app.errorhandler(404)
def not_found(e): return render_template("error.html",code=404,message="That page does not exist."),404
@app.errorhandler(500)
def server_error(e): return render_template("error.html",code=500,message="Something went wrong. Please try again."),500

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
