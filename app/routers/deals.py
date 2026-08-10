from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_scoped_client
from app.core.supabase import get_anon_client
from app.models.deal import DealCreate, DealOut

router = APIRouter(tags=["deals"])


@router.get("/deals", response_model=list[DealOut])
def list_active_deals(limit: int = Query(20, le=100)):
    """Public: currently-running deals across all shops, for the homepage strip."""
    now = datetime.now(timezone.utc).isoformat()
    client = get_anon_client()
    res = (
        client.table("deals")
        .select("*")
        .eq("is_active", True)
        .lte("starts_at", now)
        .gte("ends_at", now)
        .order("ends_at")
        .limit(limit)
        .execute()
    )
    return res.data


@router.get("/shops/{shop_id}/deals", response_model=list[DealOut])
def list_shop_deals(shop_id: UUID):
    """Public: a shop's active deals."""
    client = get_anon_client()
    res = client.table("deals").select("*").eq("shop_id", str(shop_id)).eq("is_active", True).execute()
    return res.data


@router.post("/shops/{shop_id}/deals", response_model=DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(shop_id: UUID, payload: DealCreate, client=Depends(get_scoped_client)):
    """Shop owner: launch a time-boxed offer on their shop or one product."""
    row = payload.model_dump(mode="json", exclude_none=True)
    row["shop_id"] = str(shop_id)
    res = client.table("deals").insert(row).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couldn't create the deal — check that you own this shop.",
        )
    return res.data[0]


@router.patch("/deals/{deal_id}/deactivate", response_model=DealOut)
def deactivate_deal(deal_id: UUID, client=Depends(get_scoped_client)):
    """Shop owner: end a deal early."""
    res = client.table("deals").update({"is_active": False}).eq("id", str(deal_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found, or you don't have permission to edit it.",
        )
    return res.data[0]
