# Yours Mart

Yours Mart is a Flask-based AI fashion marketplace rebuilt from the original Flask/SQLite app into a deployment-ready commerce foundation.

## Included
- Premium responsive fashion marketplace UI.
- Database-backed products with slugs, brands, categories, pricing, discounts, ratings, sizes, colours, tags and image URLs.
- Search, category/brand/price/size/rating filters and sorting.
- Persistent cart and wishlist.
- Password hashing, secure sessions and CSRF protection.
- Manual Easypaisa / bank-transfer checkout with stock validation, payment-reference capture, proof upload and real orders/order-items.
- Customer account, orders and wishlist.
- Separate customer/admin/superadmin authentication, RBAC permissions, product/category/order management, inventory ledger, payment verification, customer management, audit logs, and sales/customer/stock metrics.
- Catalog-grounded AI Fashion Assistant with optional LLM enhancement.
- Real AI Virtual Try-On using the configured FASHN provider; when the provider is unavailable or unconfigured, the UI reports the failure instead of fabricating an image.
- Optional Cloudinary image storage.
- PostgreSQL production support with SQLite local fallback.
- Vercel serverless entrypoint and environment-based secrets.

## Local setup
1. Use Python 3.11+.
2. Create a virtual environment.
3. Install dependencies with pip install -r requirements.txt.
4. Copy .env.example to .env.
5. Set a strong SECRET_KEY.
6. Use DATABASE_URL=sqlite:///yours_mart.db locally or PostgreSQL in production.
7. Generate an admin hash with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('CHANGE_THIS'))"
8. Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH.
9. Run python app.py.
10. Open http://localhost:5000.

## AI Virtual Try-On
Default provider: FASHN (or another compatible provider configured through the environment).
AI_API_URL=https://api.fashn.ai
AI_MODEL=tryon-max
AI_API_KEY=server-side-key

The API key is never sent to the browser. Customer photos are handled in memory and passed to the configured AI provider for generation. Review provider privacy/retention settings and obtain user consent before production use.

If AI_API_KEY is absent, the flow explicitly reports that live AI Try-On is unavailable; no fake/generated placeholder is returned.

## AI Fashion Assistant
Optional LLM enhancement uses an OpenAI-compatible chat-completions endpoint:
AI_ASSISTANT_API_KEY
AI_ASSISTANT_API_URL
AI_ASSISTANT_MODEL

Without these variables, the assistant still recommends actual products from the Yours Mart catalog.

## Cloud images
For production uploads configure CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.

## Vercel
Configure production environment variables in Vercel. The entrypoint is api/index.py and vercel.json routes requests to it. Use PostgreSQL for production rather than SQLite.

Typical deployment commands:
vercel
vercel --prod

## Git workflow
The production-ready implementation is maintained on main. Feature work should use short-lived branches and pull requests.

## Security
Never commit .env files, API keys, admin passwords, customer photos or private generated assets. Use HTTPS, strong secrets, PostgreSQL and cloud storage in production.

## Payment
Only manual Easypaisa / bank transfer is accepted. Customers submit a transaction/reference number plus payment screenshot; orders remain in payment verification until an authorized admin verifies or rejects the proof. The configured account defaults to 03352935407 and is controlled through environment variables. No card number or CVV is collected.
