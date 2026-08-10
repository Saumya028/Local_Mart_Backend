from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import require_role
from app.core.supabase import get_service_client
from app.models.order import OrderOut
from app.models.shop import ShopOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])

# Admin routes use the service-role client deliberately: an admin's job is
# platform-wide oversight across every shop, which per-shop RLS policies
# don't (and shouldn't) grant directly. Access to this router itself is
# gated by the require_role("admin") dependency above.


@router.get("/shops/pending", response_model=list[ShopOut])
def list_pending_shops():
    """Shops awaiting verification before they appear to customers."""
    client = get_service_client()
    res = client.table("shops").select("*").eq("is_verified", False).order("created_at").execute()
    return res.data


@router.patch("/shops/{shop_id}/verify", response_model=ShopOut)
def verify_shop(shop_id: UUID):
    client = get_service_client()
    res = client.table("shops").update({"is_verified": True}).eq("id", str(shop_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found.")
    return res.data[0]


@router.patch("/shops/{shop_id}/reject", response_model=ShopOut)
def reject_shop(shop_id: UUID):
    """Keeps the shop unverified (hidden) rather than deleting it, so the
    owner can fix and resubmit."""
    client = get_service_client()
    res = client.table("shops").update({"is_verified": False}).eq("id", str(shop_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found.")
    return res.data[0]


@router.get("/orders", response_model=list[OrderOut])
def list_all_orders(
    shop_id: UUID | None = None,
    limit: int = Query(50, le=200),
):
    """Platform-wide order oversight, e.g. for dispute resolution."""
    client = get_service_client()
    query = client.table("orders").select("*, order_items(*)")
    if shop_id:
        query = query.eq("shop_id", str(shop_id))
    res = query.order("placed_at", desc=True).limit(limit).execute()
    return res.data
