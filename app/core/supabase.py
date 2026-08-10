from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings

settings = get_settings()


@lru_cache
def get_service_client() -> Client:
    """
    Privileged client authenticated with the service-role key.
    Bypasses Row-Level Security entirely — use only in admin-only routes
    or trusted background jobs, never for arbitrary user-supplied queries.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache
def get_anon_client() -> Client:
    """
    Unauthenticated client using the anon key. Still evaluated against RLS —
    used for public browsing endpoints (categories, verified shops, active
    products) so we're not bypassing policies just because no one's logged in.
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_user_client(access_token: str) -> Client:
    """
    Client authenticated as the calling user. Uses the anon key for the
    apikey header and the user's own JWT as the Authorization bearer, so
    every query is evaluated against Postgres RLS policies as that user —
    Postgres, not this API layer, is the source of truth for permissions.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
