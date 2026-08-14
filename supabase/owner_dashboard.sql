-- ============================================================================
-- LocalMart — owner dashboard additions
-- Run in the Supabase SQL editor AFTER schema.sql (and seed.sql if used).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Custom Access Token Hook — stamps the caller's profiles.role onto the JWT
-- as app_metadata.role, which app/core/security.py's require_role() reads.
-- Without this, every token defaults to role 'customer' regardless of what's
-- in the profiles table, so shop-owner-only endpoints (POST /shops, etc.)
-- would 403 for real shop owners.
--
-- IMPORTANT — a SQL script alone can't finish this setup. After running this
-- file, go to Supabase Dashboard → Authentication → Hooks → Custom Access
-- Token, and select "public.custom_access_token_hook" as the hook function.
-- Existing sessions won't pick up the new claim until they sign in again.
-- ----------------------------------------------------------------------------
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql
stable
as $$
declare
  claims jsonb;
  user_role text;
begin
  select role into user_role from public.profiles where id = (event->>'user_id')::uuid;

  claims := coalesce(event->'claims', '{}'::jsonb);
  if user_role is not null then
    claims := jsonb_set(
      claims,
      '{app_metadata}',
      coalesce(claims->'app_metadata', '{}'::jsonb) || jsonb_build_object('role', user_role)
    );
  end if;

  event := jsonb_set(event, '{claims}', claims);
  return event;
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from authenticated, anon, public;

-- ----------------------------------------------------------------------------
-- shop_dashboard_summary — today vs. yesterday revenue/orders + pending count.
-- security invoker (default): relies on the caller's own RLS access to
-- public.orders, i.e. the "orders_customer_read" policy that already lets a
-- shop owner read orders for shops they own. No new privilege is granted.
-- ----------------------------------------------------------------------------
create or replace function public.shop_dashboard_summary(p_shop_id uuid)
returns table (
  today_revenue     numeric,
  today_orders      bigint,
  yesterday_revenue numeric,
  yesterday_orders  bigint,
  pending_orders    bigint
)
language sql stable
as $$
  select
    coalesce(sum(total) filter (
      where placed_at >= date_trunc('day', now()) and status <> 'cancelled'
    ), 0),
    count(*) filter (where placed_at >= date_trunc('day', now())),
    coalesce(sum(total) filter (
      where placed_at >= date_trunc('day', now() - interval '1 day')
        and placed_at < date_trunc('day', now())
        and status <> 'cancelled'
    ), 0),
    count(*) filter (
      where placed_at >= date_trunc('day', now() - interval '1 day')
        and placed_at < date_trunc('day', now())
    ),
    count(*) filter (where status = 'placed')
  from public.orders
  where shop_id = p_shop_id;
$$;

-- ----------------------------------------------------------------------------
-- shop_revenue_daily — one row per day for the last p_days days, zero-filled.
-- ----------------------------------------------------------------------------
create or replace function public.shop_revenue_daily(p_shop_id uuid, p_days int default 7)
returns table (day date, revenue numeric, order_count bigint)
language sql stable
as $$
  select
    d::date,
    coalesce(sum(o.total), 0),
    count(o.id)
  from generate_series(current_date - (p_days - 1), current_date, interval '1 day') d
  left join public.orders o
    on o.shop_id = p_shop_id
    and o.placed_at::date = d::date
    and o.status <> 'cancelled'
  group by d
  order by d;
$$;

-- ----------------------------------------------------------------------------
-- shop_top_products — best sellers by revenue, all-time (excludes cancelled).
-- ----------------------------------------------------------------------------
create or replace function public.shop_top_products(p_shop_id uuid, p_limit int default 5)
returns table (product_id uuid, product_name text, qty_sold bigint, revenue numeric)
language sql stable
as $$
  select oi.product_id, oi.product_name_snapshot, sum(oi.qty)::bigint, sum(oi.line_total)
  from public.order_items oi
  join public.orders o on o.id = oi.order_id
  where o.shop_id = p_shop_id and o.status <> 'cancelled'
  group by oi.product_id, oi.product_name_snapshot
  order by sum(oi.line_total) desc
  limit p_limit;
$$;

-- ----------------------------------------------------------------------------
-- shop_customers — per-customer order stats for a shop. This one IS security
-- definer with an explicit ownership check inside: profiles are otherwise
-- private (see "profiles_select_own_or_admin"), and a shop owner legitimately
-- needs to see the name/phone of people who've ordered from them, but no one
-- else's.
-- ----------------------------------------------------------------------------
create or replace function public.shop_customers(p_shop_id uuid)
returns table (
  customer_id   uuid,
  full_name     text,
  phone         text,
  order_count   bigint,
  total_spent   numeric,
  last_order_at timestamptz
)
language plpgsql
security definer set search_path = public
as $$
begin
  if not exists (
    select 1 from public.shops where id = p_shop_id and owner_id = auth.uid()
  ) and not public.is_admin() then
    raise exception 'Not authorized for this shop';
  end if;

  return query
  select o.customer_id, p.full_name, p.phone,
         count(*)::bigint, sum(o.total), max(o.placed_at)
  from public.orders o
  join public.profiles p on p.id = o.customer_id
  where o.shop_id = p_shop_id
  group by o.customer_id, p.full_name, p.phone
  order by max(o.placed_at) desc;
end;
$$;

grant execute on function public.shop_dashboard_summary(uuid) to authenticated;
grant execute on function public.shop_revenue_daily(uuid, int) to authenticated;
grant execute on function public.shop_top_products(uuid, int) to authenticated;
grant execute on function public.shop_customers(uuid) to authenticated;
