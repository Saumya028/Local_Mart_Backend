from uuid import UUID

from fastapi import APIRouter, Query

from app.core.supabase import get_anon_client
from app.models.common import ReviewOut

router = APIRouter(tags=["reviews"])


@router.get("/shops/{shop_id}/reviews", response_model=list[ReviewOut])
def list_shop_reviews(shop_id: UUID, limit: int = Query(50, le=200)):
    """Public: a shop's customer reviews, newest first."""
    client = get_anon_client()
    res = (
        client.table("reviews")
        .select("*")
        .eq("shop_id", str(shop_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data
