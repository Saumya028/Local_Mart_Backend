-- Sample data matching the LocalMart landing page, for local dev.
-- Run after schema.sql. Assumes at least one auth.users row exists per
-- owner (create shop-owner test users via Supabase Auth first, then
-- replace the placeholder UUIDs below with their real ids).

insert into public.categories (name, slug, emoji, sort_order) values
  ('Groceries',    'groceries',    '🥬', 1),
  ('Bakery',       'bakery',       '🥐', 2),
  ('Pharmacy',     'pharmacy',     '💊', 3),
  ('Electronics',  'electronics',  '🎧', 4),
  ('Fashion',      'fashion',      '👗', 5),
  ('Stationery',   'stationery',   '✏️', 6),
  ('Home & Living','home-living',  '🏠', 7),
  ('Restaurants',  'restaurants',  '🍽️', 8);

-- Replace :owner_id with a real profiles.id (== auth.users.id) before running.
-- insert into public.shops (owner_id, name, slug, category_id, address, lat, lng, is_open, is_verified, avg_delivery_minutes)
-- select :'owner_id', 'Green Basket Organics', 'green-basket-organics', id, 'Koramangala, Bengaluru', 12.9352, 77.6146, true, true, 15
-- from public.categories where slug = 'groceries';
