from fastapi import APIRouter

from app.core.supabase import get_anon_client
from app.models.common import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories():
    """Public: full category taxonomy, used for the browse-by-category strip."""
    client = get_anon_client()
    res = client.table("categories").select("*").order("sort_order").execute()
    return res.data
