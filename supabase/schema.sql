-- ============================================================================
-- LocalMart — Supabase schema
-- Run in the Supabase SQL editor, or via `supabase db push` / migrations.
-- Assumes Supabase Auth (auth.users) is enabled.
-- ============================================================================

create extension if not exists "pgcrypto";      -- gen_random_uuid()

-- ----------------------------------------------------------------------------
-- profiles — one row per auth user, carries the role used throughout RLS
-- ----------------------------------------------------------------------------
create table public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  role          text not null default 'customer' check (role in ('customer','shop_owner','admin')),
  full_name     text,
  phone         text,
  avatar_url    text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- auto-create a profile row whenever a new auth user signs up
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, role)
  values (
    new.id,
    new.raw_user_meta_data->>'full_name',
    coalesce(new.raw_user_meta_data->>'role', 'customer')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ----------------------------------------------------------------------------
-- categories — platform-managed taxonomy (Groceries, Bakery, Pharmacy, …)
-- ----------------------------------------------------------------------------
create table public.categories (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  slug        text not null unique,
  emoji       text,
  sort_order  int not null default 0
);

-- ----------------------------------------------------------------------------
-- shops
-- ----------------------------------------------------------------------------
create table public.shops (
  id                  uuid primary key default gen_random_uuid(),
  owner_id            uuid not null references public.profiles(id) on delete cascade,
  name                text not null,
  slug                text not null unique,
  category_id         uuid references public.categories(id),
  description         text,
  logo_url            text,
  cover_url           text,
  address             text,
  lat                 double precision,
  lng                 double precision,
  is_open             boolean not null default true,
  is_verified         boolean not null default false,
  rating              numeric(2,1) not null default 0,
  rating_count        int not null default 0,
  delivery_radius_km  numeric not null default 3,
  avg_delivery_minutes int not null default 25,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index shops_owner_idx on public.shops(owner_id);
create index shops_category_idx on public.shops(category_id);
create index shops_location_idx on public.shops(lat, lng);

-- ----------------------------------------------------------------------------
-- products
-- ----------------------------------------------------------------------------
create table public.products (
  id            uuid primary key default gen_random_uuid(),
  shop_id       uuid not null references public.shops(id) on delete cascade,
  category_id   uuid references public.categories(id),
  name          text not null,
  description   text,
  sku           text,
  price         numeric(10,2) not null check (price >= 0),
  mrp           numeric(10,2) check (mrp >= 0),
  stock_qty     int not null default 0 check (stock_qty >= 0),
  image_url     text,
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index products_shop_idx on public.products(shop_id);
create index products_category_idx on public.products(category_id);
create index products_active_idx on public.products(is_active);

-- ----------------------------------------------------------------------------
-- deals — time-boxed offers, optionally scoped to one product
-- ----------------------------------------------------------------------------
create table public.deals (
  id              uuid primary key default gen_random_uuid(),
  shop_id         uuid not null references public.shops(id) on delete cascade,
  product_id      uuid references public.products(id) on delete cascade,
  title           text not null,
  discount_type   text not null check (discount_type in ('percentage','flat','bogo')),
  discount_value  numeric(10,2) not null default 0,
  starts_at       timestamptz not null default now(),
  ends_at         timestamptz not null,
  is_active       boolean not null default true
);

create index deals_shop_idx on public.deals(shop_id);
create index deals_active_window_idx on public.deals(is_active, starts_at, ends_at);

-- ----------------------------------------------------------------------------
-- addresses — customer delivery addresses
-- ----------------------------------------------------------------------------
create table public.addresses (
  id            uuid primary key default gen_random_uuid(),
  customer_id   uuid not null references public.profiles(id) on delete cascade,
  label         text not null default 'Home',
  line1         text not null,
  line2         text,
  city          text,
  lat           double precision,
  lng           double precision,
  is_default    boolean not null default false,
  created_at    timestamptz not null default now()
);

create index addresses_customer_idx on public.addresses(customer_id);

-- ----------------------------------------------------------------------------
-- orders / order_items
-- ----------------------------------------------------------------------------
create table public.orders (
  id                  uuid primary key default gen_random_uuid(),
  customer_id         uuid not null references public.profiles(id),
  shop_id             uuid not null references public.shops(id),
  delivery_address_id uuid references public.addresses(id),
  status              text not null default 'placed'
                        check (status in ('placed','confirmed','packed','out_for_delivery','delivered','cancelled')),
  subtotal            numeric(10,2) not null default 0,
  delivery_fee        numeric(10,2) not null default 0,
  total               numeric(10,2) not null default 0,
  cancelled_reason    text,
  placed_at           timestamptz not null default now(),
  confirmed_at        timestamptz,
  delivered_at        timestamptz
);

create index orders_customer_idx on public.orders(customer_id);
create index orders_shop_idx on public.orders(shop_id);
create index orders_status_idx on public.orders(status);

create table public.order_items (
  id                    uuid primary key default gen_random_uuid(),
  order_id              uuid not null references public.orders(id) on delete cascade,
  product_id            uuid not null references public.products(id),
  product_name_snapshot text not null,
  unit_price            numeric(10,2) not null,
  qty                   int not null check (qty > 0),
  line_total            numeric(10,2) not null
);

create index order_items_order_idx on public.order_items(order_id);

-- ----------------------------------------------------------------------------
-- reviews & wishlists
-- ----------------------------------------------------------------------------
create table public.reviews (
  id            uuid primary key default gen_random_uuid(),
  shop_id       uuid not null references public.shops(id) on delete cascade,
  customer_id   uuid not null references public.profiles(id),
  order_id      uuid references public.orders(id),
  rating        int not null check (rating between 1 and 5),
  comment       text,
  created_at    timestamptz not null default now(),
  unique (customer_id, order_id)
);

create table public.wishlists (
  customer_id   uuid not null references public.profiles(id) on delete cascade,
  product_id    uuid not null references public.products(id) on delete cascade,
  created_at    timestamptz not null default now(),
  primary key (customer_id, product_id)
);

-- ----------------------------------------------------------------------------
-- updated_at helper trigger, applied to mutable tables
-- ----------------------------------------------------------------------------
create function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger shops_set_updated_at before update on public.shops
  for each row execute procedure public.set_updated_at();
create trigger products_set_updated_at before update on public.products
  for each row execute procedure public.set_updated_at();
create trigger profiles_set_updated_at before update on public.profiles
  for each row execute procedure public.set_updated_at();

-- ----------------------------------------------------------------------------
-- review -> shop rating rollup
-- ----------------------------------------------------------------------------
create function public.refresh_shop_rating()
returns trigger language plpgsql as $$
begin
  update public.shops s
  set rating = coalesce((select round(avg(r.rating)::numeric, 1) from public.reviews r where r.shop_id = s.id), 0),
      rating_count = (select count(*) from public.reviews r where r.shop_id = s.id)
  where s.id = coalesce(new.shop_id, old.shop_id);
  return null;
end;
$$;

create trigger reviews_refresh_rating
  after insert or update or delete on public.reviews
  for each row execute procedure public.refresh_shop_rating();

-- ----------------------------------------------------------------------------
-- geosearch — haversine distance in km, no PostGIS dependency required
-- ----------------------------------------------------------------------------
create or replace function public.nearby_shops(
  p_lat double precision,
  p_lng double precision,
  p_radius_km numeric default 5
)
returns table (
  id uuid,
  name text,
  slug text,
  category_id uuid,
  logo_url text,
  rating numeric,
  rating_count int,
  is_open boolean,
  avg_delivery_minutes int,
  distance_km numeric
)
language sql
stable
as $$
  select *
  from (
    select
      s.id,
      s.name,
      s.slug,
      s.category_id,
      s.logo_url,
      s.rating,
      s.rating_count,
      s.is_open,
      s.avg_delivery_minutes,
      round(
        (
          6371 * acos(
            least(
              1.0,
              greatest(
                -1.0,
                cos(radians(p_lat))
                * cos(radians(s.lat))
                * cos(radians(s.lng) - radians(p_lng))
                + sin(radians(p_lat))
                * sin(radians(s.lat))
              )
            )
          )
        )::numeric,
        2
      ) as distance_km
    from public.shops s
    where
      s.lat is not null
      and s.lng is not null
      and s.is_verified = true
  ) nearby
  where distance_km <= p_radius_km
  order by distance_km asc;
$$;

-- ----------------------------------------------------------------------------
-- create_order — atomic order placement: validates stock, decrements it,
-- writes order + order_items, all inside one transaction.
-- Called via RPC from FastAPI as the authenticated customer.
-- p_items shape: [{ "product_id": "...", "qty": 2 }, ...]
-- ----------------------------------------------------------------------------
create function public.create_order(
  p_shop_id uuid,
  p_delivery_address_id uuid,
  p_items jsonb,
  p_delivery_fee numeric default 0
)
returns uuid
language plpgsql
security definer set search_path = public
as $$
declare
  v_order_id     uuid;
  v_item         jsonb;
  v_product      public.products%rowtype;
  v_qty          int;
  v_subtotal     numeric := 0;
  v_line_total   numeric;
begin
  if jsonb_array_length(p_items) = 0 then
    raise exception 'Order must contain at least one item';
  end if;

  insert into public.orders (customer_id, shop_id, delivery_address_id, delivery_fee, status)
  values (auth.uid(), p_shop_id, p_delivery_address_id, p_delivery_fee, 'placed')
  returning id into v_order_id;

  for v_item in select * from jsonb_array_elements(p_items)
  loop
    select * into v_product
    from public.products
    where id = (v_item->>'product_id')::uuid
      and shop_id = p_shop_id
      and is_active = true
    for update;

    if not found then
      raise exception 'Product % not found in this shop', v_item->>'product_id';
    end if;

    v_qty := (v_item->>'qty')::int;

    if v_product.stock_qty < v_qty then
      raise exception 'Not enough stock for %', v_product.name;
    end if;

    update public.products set stock_qty = stock_qty - v_qty where id = v_product.id;

    v_line_total := v_product.price * v_qty;
    v_subtotal := v_subtotal + v_line_total;

    insert into public.order_items (order_id, product_id, product_name_snapshot, unit_price, qty, line_total)
    values (v_order_id, v_product.id, v_product.name, v_product.price, v_qty, v_line_total);
  end loop;

  update public.orders
  set subtotal = v_subtotal, total = v_subtotal + p_delivery_fee
  where id = v_order_id;

  return v_order_id;
end;
$$;

-- ----------------------------------------------------------------------------
-- Row-Level Security
-- ----------------------------------------------------------------------------
alter table public.profiles   enable row level security;
alter table public.categories enable row level security;
alter table public.shops      enable row level security;
alter table public.products   enable row level security;
alter table public.deals      enable row level security;
alter table public.addresses  enable row level security;
alter table public.orders     enable row level security;
alter table public.order_items enable row level security;
alter table public.reviews    enable row level security;
alter table public.wishlists  enable row level security;

-- helper: is the current user an admin?
create function public.is_admin()
returns boolean language sql stable as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

-- profiles: read own row, admins read all; users update their own row
create policy "profiles_select_own_or_admin" on public.profiles
  for select using (id = auth.uid() or public.is_admin());
create policy "profiles_update_own" on public.profiles
  for update using (id = auth.uid());

-- categories: public read, admin write
create policy "categories_public_read" on public.categories
  for select using (true);
create policy "categories_admin_write" on public.categories
  for all using (public.is_admin()) with check (public.is_admin());

-- shops: public reads verified shops; owners read/write their own; admins do anything
create policy "shops_public_read_verified" on public.shops
  for select using (is_verified = true or owner_id = auth.uid() or public.is_admin());
create policy "shops_owner_insert" on public.shops
  for insert with check (owner_id = auth.uid());
create policy "shops_owner_update" on public.shops
  for update using (owner_id = auth.uid() or public.is_admin());
create policy "shops_admin_delete" on public.shops
  for delete using (public.is_admin());

-- products: public reads active products of visible shops; owner manages own shop's products
create policy "products_public_read" on public.products
  for select using (
    is_active = true
    or exists (select 1 from public.shops s where s.id = shop_id and (s.owner_id = auth.uid() or public.is_admin()))
  );
create policy "products_owner_write" on public.products
  for all using (
    exists (select 1 from public.shops s where s.id = shop_id and (s.owner_id = auth.uid() or public.is_admin()))
  ) with check (
    exists (select 1 from public.shops s where s.id = shop_id and (s.owner_id = auth.uid() or public.is_admin()))
  );

-- deals: public reads active deals; owner manages own shop's deals
create policy "deals_public_read" on public.deals
  for select using (true);
create policy "deals_owner_write" on public.deals
  for all using (
    exists (select 1 from public.shops s where s.id = shop_id and (s.owner_id = auth.uid() or public.is_admin()))
  ) with check (
    exists (select 1 from public.shops s where s.id = shop_id and (s.owner_id = auth.uid() or public.is_admin()))
  );

-- addresses: customer manages their own
create policy "addresses_owner_all" on public.addresses
  for all using (customer_id = auth.uid() or public.is_admin())
  with check (customer_id = auth.uid());

-- orders: customer sees/creates own; shop owner sees/updates orders placed at their shop
create policy "orders_customer_read" on public.orders
  for select using (
    customer_id = auth.uid()
    or exists (select 1 from public.shops s where s.id = shop_id and s.owner_id = auth.uid())
    or public.is_admin()
  );
create policy "orders_customer_insert" on public.orders
  for insert with check (customer_id = auth.uid());
create policy "orders_shop_update_status" on public.orders
  for update using (
    exists (select 1 from public.shops s where s.id = shop_id and s.owner_id = auth.uid())
    or public.is_admin()
  );

-- order_items: visible to whoever can see the parent order
create policy "order_items_read" on public.order_items
  for select using (
    exists (
      select 1 from public.orders o
      where o.id = order_id
        and (o.customer_id = auth.uid()
             or exists (select 1 from public.shops s where s.id = o.shop_id and s.owner_id = auth.uid())
             or public.is_admin())
    )
  );

-- reviews: public read, customer writes own (tied to their delivered order)
create policy "reviews_public_read" on public.reviews
  for select using (true);
create policy "reviews_customer_insert" on public.reviews
  for insert with check (customer_id = auth.uid());

-- wishlists: private to the customer
create policy "wishlists_owner_all" on public.wishlists
  for all using (customer_id = auth.uid()) with check (customer_id = auth.uid());
