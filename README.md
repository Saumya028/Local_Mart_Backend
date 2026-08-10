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
FastAPI  ──▶  app/core/security.py   decodes the JWT, builds a per-request
      │                              Supabase client scoped to that user
      ▼
Supabase Postgres (RLS enforced) ──▶ tables + create_order()/nearby_shops() RPCs
```

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

1. Create a Supabase project, then run `supabase/schema.sql` in the SQL
   editor (or via `supabase db push` if you're using the CLI), followed by
   `supabase/seed.sql`.
2. Copy `.env.example` to `.env` and fill in your project's URL and keys
   (Project Settings → API).
3. Install and run:

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
  trigger) with `role = 'customer'` by default. To make someone a
  `shop_owner` or `admin`, set `role` in their `raw_user_meta_data` at
  signup, or update `profiles.role` directly — and keep the JWT's
  `app_metadata.role` claim in sync (e.g. via a Supabase Auth Hook), since
  `require_role()` reads that claim, not the `profiles` table, to avoid an
  extra DB round-trip on every request.

## Still to build

- **Shopkeeper dashboard** and **admin panel** (Next.js) that consume this
  API — this backend has everything they need (inventory CRUD, order queue
  with status transitions, shop verification queue, platform order
  oversight).
- Payments/webhooks, push notifications for order status changes, and
  review-writing tied to delivered orders (`reviews` table already supports
  it; no endpoint yet).
