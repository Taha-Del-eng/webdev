# Yours Mart

Yours Mart is a Flask-based AI fashion marketplace rebuilt from the original Flask/SQLite app into a deployment-ready commerce foundation.

## Included
- Premium responsive fashion marketplace UI.
- Database-backed products with slugs, brands, categories, pricing, discounts, ratings, sizes, colours, tags and image URLs.
- Search, category/brand/price/size/rating filters and sorting.
- Persistent cart and wishlist.
- Password hashing, secure sessions and CSRF protection.
- Cash-on-Delivery checkout with stock validation and real orders/order-items.
- Customer account, orders and wishlist.
- Admin product/category/order management plus sales/customer/stock metrics.
- Catalog-grounded AI Fashion Assistant with optional LLM enhancement.
- Real AI Virtual Try-On using FASHN Try-On Max when configured, with an explicit demo/mock fallback.
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
Default provider: FASHN.
AI_API_URL=https://api.fashn.ai
AI_MODEL=tryon-max
AI_API_KEY=server-side-key

The API key is never sent to the browser. Customer photos are handled in memory and passed to the configured AI provider for generation. Review provider privacy/retention settings and obtain user consent before production use.

If AI_API_KEY is absent, the flow explicitly reports demo/mock mode instead of pretending a live generation happened.

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
The implementation is on feature/yours-mart-ai-marketplace for review before merging into main.

## Security
Never commit .env files, API keys, admin passwords, customer photos or private generated assets. Use HTTPS, strong secrets, PostgreSQL and cloud storage in production.

## Payment
Cash on Delivery is implemented. No card number or CVV is collected. The payment model can be extended later for Stripe or a local Pakistan provider.
