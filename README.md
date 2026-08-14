# LocalMart API

FastAPI backend for the LocalMart marketplace, backed by Supabase Postgres.
Handles customer browsing/ordering, shopkeeper inventory & order management,
and admin oversight.

## Architecture

**Postgres RLS is the source of truth for authorization, not this API.**
Every request (except admin routes) is made through a Supabase client
authenticated as the calling user — their JWT is forwarded as the bearer
token on every query, so Postgres' Row-Level Security policies decide what
they can see and write. This API layer validates shapes, enforces the order
status state machine, and wires HTTP to Postgres — it does not duplicate
permission checks that the database already enforces.

```
Next.js frontend
      │  Authorization: Bearer <supabase JWT>
      ▼
FastAPI  ──▶  app/core/security.py   verifies the JWT (JWKS by default; see
      │                              below), builds a per-request Supabase
      │                              client scoped to that user
      ▼
Supabase Postgres (RLS enforced) ──▶ tables + create_order()/nearby_shops() RPCs
```

`app/core/security.py` verifies each token against Supabase's public JWKS
endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) — this is what
current Supabase projects need, since new projects default to asymmetric
(ES256) JWT Signing Keys rather than a shared secret. If a token's header
says `alg: HS256` instead, it falls back to verifying against
`SUPABASE_JWT_SECRET` — only relevant for older projects still on the
legacy shared secret (Project Settings → API → JWT Keys → "Legacy JWT
Secret" tab); leave that env var blank otherwise.

Admin routes (`/admin/*`) are the one exception: they use a service-role
client that bypasses RLS, because "see every shop across the platform" isn't
something a per-shop policy should grant. Access to that router is gated by
`require_role("admin")` on the JWT's `app_metadata.role` claim instead.

Order placement goes through a single Postgres function, `create_order()`
(see `supabase/schema.sql`), so stock validation, the stock decrement, and
the order + order_items writes happen in one transaction — two customers
can't both buy the last unit of something.

## Project layout

```
app/
  main.py                FastAPI app, CORS, router registration
  core/
    config.py              Settings (env vars)
    supabase.py             Client factories: service / anon / per-user
    security.py              JWT decoding, get_current_user, require_role()
  models/                  Pydantic request/response schemas
  routers/
    categories.py            GET /categories
    shops.py                  Shop CRUD, discovery, /shops/nearby
    products.py                Product CRUD + stock updates, scoped to a shop
    deals.py                    Deal CRUD, active-deals listing
    addresses.py                 Customer delivery addresses
    orders.py                     Place orders, list/view, status transitions
    profile.py                     GET/PATCH the caller's own profile
    admin.py                        Shop verification, platform-wide orders
supabase/
  schema.sql               Full schema: tables, RLS policies, RPC functions
  seed.sql                   Categories + sample data for local dev
```

## Setup

1. Create a Supabase project, then run in the SQL editor, in order:
   `supabase/schema.sql` → `supabase/seed.sql` → `supabase/owner_dashboard.sql`.
2. **Enable the Custom Access Token Hook** (required for shop-owner and admin
   routes to work): Supabase Dashboard → Authentication → Hooks → Custom
   Access Token → select `public.custom_access_token_hook`. Without this,
   every JWT reports role `customer` regardless of `profiles.role`, so
   `POST /shops` and everything under `/admin` will 403 for real shop
   owners/admins. Anyone already signed in needs to sign out and back in to
   pick up the new claim.
3. Copy `.env.example` to `.env` and fill in your project's URL and keys
   (Project Settings → API).
4. Install and run:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

## Auth notes

- The frontend authenticates with Supabase Auth (`supabase-js`) directly and
  sends the resulting access token as `Authorization: Bearer <token>` on
  every FastAPI request.
- A new signup gets a `profiles` row automatically (`handle_new_user()`
  trigger), with `role` taken from `raw_user_meta_data.role` at signup
  (defaults to `customer` if omitted) — the frontend's sign-up form passes
  `customer` or `shop_owner` here directly. To promote someone to `admin`,
  update `profiles.role` directly in the database (there's no self-serve
  admin signup).
- `custom_access_token_hook()` (in `supabase/owner_dashboard.sql`) stamps
  that `profiles.role` onto the JWT as `app_metadata.role` at token-mint
  time, which is what `require_role()` actually checks — see step 2 above.

## Still to build

- Payments/webhooks, push notifications for order status changes, and
  review-writing tied to delivered orders (`reviews` table already supports
  it; no endpoint yet).
- Admin panel is minimal (shop verification queue only) — platform-wide
  order oversight (`GET /admin/orders`) has no frontend yet.
