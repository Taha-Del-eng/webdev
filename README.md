# Yours Mart

Yours Mart is a Flask-based fashion marketplace with customer accounts, catalog browsing, cart and checkout, vendor stores, role-separated admin tooling, manual Easypaisa/bank-transfer verification, a catalog-grounded AI assistant, and a virtual try-on adapter.

## Included

- Responsive fashion marketplace with database-backed products, search, filters, sorting, cart, and wishlist.
- Password hashing, secure sessions, CSRF protection, and a separate JWT bearer API with refresh-token rotation.
- Manual Easypaisa / bank transfer checkout with payment proof upload and admin review.
- Separate customer, vendor, admin, and superadmin permissions.
- Catalog-grounded assistant, with optional external LLM enhancement.
- Virtual try-on adapter for genuine external provider jobs; no fake images or mock success.
- Optional Cloudinary storage and PostgreSQL support, with SQLite local fallback.

## Local setup

Use a Python version supported by the project's installed dependencies, create a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, set strong local secrets, and run `python app.py`. Keep `.env` out of Git.

## AI Virtual Try-On status

The current application has a real FASHN-compatible external-provider path. It needs an authorized provider key and may incur provider charges. Configure `AI_TRYON_BACKEND=provider`, `AI_API_URL=https://api.fashn.ai`, `AI_MODEL=tryon-max`, and set `AI_API_KEY` privately. The server does not send the key to the browser. Customer photos are transmitted to the configured provider for processing; disclose this and obtain consent before production use.

### Local, zero-cost inference

Set `AI_TRYON_BACKEND=local` only to select the local mode explicitly. At present, a production-suitable local model adapter and weights are **not bundled or installed**, so this mode fails closed with a clear message rather than returning a fabricated result. No model weights are downloaded automatically.

The hardware described for local development (about 7.7 GB RAM, Intel Iris Xe integrated graphics, no NVIDIA GPU) is not a safe basis for promising practical inference for the popular high-quality diffusion-based try-on models. Model repositories and weights have varying licenses; some are research/non-commercial only. This project does not select or bundle a model until both commercial-use rights and realistic hardware requirements are verified. Local try-on is therefore **not currently operational**; provider-backed generation is only operational when the external API is configured and reachable.

### Security and image handling

The adapter accepts only JPG, PNG, and WebP image MIME types for uploaded person images, caps raw image bytes at 8 MiB, applies finite request timeouts, avoids returning provider response bodies, and reports unavailable inference honestly. The `/api/tryon/<product_id>` route validates decoded image bytes and dimensions with Pillow before calling the adapter. The Try-On page now makes the unavailable state explicit when no provider key is configured and explains that external provider retention policies apply. Review provider privacy/retention terms before using real customer photos.

## AI Fashion Assistant

Optional LLM enhancement uses an OpenAI-compatible chat-completions endpoint via `AI_ASSISTANT_API_KEY`, `AI_ASSISTANT_API_URL`, and `AI_ASSISTANT_MODEL`. Without those settings, the assistant can still recommend products from the catalog.

## Cloud images

For production uploads, configure `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`.

## JWT API and vendor stores

- `GET /api/auth/csrf` returns a CSRF token for JSON POST requests.
- `POST /api/auth/signup` and `POST /api/auth/login` issue bearer tokens.
- `POST /api/auth/refresh` rotates a refresh token and revokes its predecessor.
- `POST /api/auth/logout` revokes a refresh token.
- `GET /api/v1/me` and `GET /api/v1/orders` require `Authorization: Bearer <access_token>`.

Set `JWT_SECRET_KEY` to a strong random secret. Access tokens default to 15 minutes (maximum one hour); refresh tokens default to 14 days (maximum 30 days). JSON POST requests must include `X-CSRFToken` from `/api/auth/csrf`.

Vendor stores require platform approval. Mixed-store checkout is blocked until split-order fulfillment is supported. Login and API signup endpoints have per-IP rate limits; configure shared Redis for multi-worker production.

## Deployment and security

Configure production environment variables in your deployment platform and use PostgreSQL for production rather than SQLite. Never commit `.env`, API keys, admin passwords, customer photos, or private generated assets. Use HTTPS and strong secrets.

## Payment

Only manual Easypaisa / bank transfer is accepted. Customers submit a transaction/reference number and payment screenshot; orders remain pending verification until an authorized admin verifies or rejects the proof. No live payment provider verifies transfers. If an admin cancels an order after a verified payment, its status becomes Refund Pending; an authorized admin can mark it Refunded after handling the refund manually. The initial payment account and shipping defaults come from environment variables, then are stored in the database for superadmin configuration. Superadmin can change the Easypaisa destination, display name, delivery fee, and free-shipping threshold. These settings affect future checkouts only. No card number or CVV is collected.


## Verification and test data

Run `python verify_app.py` for the isolated marketplace smoke suite and `python -m unittest discover -s tests -v` for focused service tests. The smoke script now creates its SQLite database in a unique temporary directory and cleans up only that database; it no longer deletes a pre-existing `verify_yours_mart.db` in the project directory. GitHub Actions runs both commands on the marketplace feature branch and on pull requests targeting the configured integration branches.

The application initializes a starter catalog only when the selected database has no products. Those starter catalog entries are demo merchandise for local development, not verified real inventory or live offers. Do not use a database seeded with demo products as a production catalog without reviewing and replacing the data.

Uploaded product images and payment proofs are checked against their decoded image format, file-size cap, pixel dimensions, and animation support. Local uploads are kept under the ignored `instance/` directory; payment proofs are stored separately from public product media.
