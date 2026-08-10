from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import CurrentUser, get_current_user, get_scoped_client, require_role
from app.core.supabase import get_anon_client
from app.models.shop import NearbyShopOut, ShopCreate, ShopOut, ShopUpdate

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
def list_shops(
    category_id: Optional[UUID] = None,
    q: Optional[str] = Query(None, description="Search shop names"),
    slug: Optional[str] = Query(None, description="Exact-match a single shop by its slug"),
    limit: int = Query(20, le=100),
    offset: int = 0,
):
    """Public: browse verified shops, optionally filtered by category, name, or exact slug."""
    client = get_anon_client()
    query = client.table("shops").select("*").eq("is_verified", True)
    if category_id:
        query = query.eq("category_id", str(category_id))
    if q:
        query = query.ilike("name", f"%{q}%")
    if slug:
        query = query.eq("slug", slug)
    res = query.range(offset, offset + limit - 1).order("rating", desc=True).execute()
    return res.data


@router.get("/nearby", response_model=list[NearbyShopOut])
def nearby_shops(
    lat: float,
    lng: float,
    radius_km: float = Query(5, gt=0, le=50),
):
    """Public: shops within radius_km of (lat, lng), nearest first."""
    client = get_anon_client()
    res = client.rpc(
        "nearby_shops", {"p_lat": lat, "p_lng": lng, "p_radius_km": radius_km}
    ).execute()
    return res.data


@router.get("/{shop_id}", response_model=ShopOut)
def get_shop(shop_id: UUID):
    """Public: a single shop's storefront details."""
    client = get_anon_client()
    res = client.table("shops").select("*").eq("id", str(shop_id)).single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shop not found.")
    return res.data


@router.post("", response_model=ShopOut, status_code=status.HTTP_201_CREATED)
def create_shop(
    payload: ShopCreate,
    user: CurrentUser = Depends(require_role("shop_owner", "admin")),
    client=Depends(get_scoped_client),
):
    """
    Shop owner: list a new shop. New shops start unverified — they go live
    to customers once an admin approves them via the verification queue.
    """
    row = payload.model_dump(mode="json", exclude_none=True)
    row["owner_id"] = user.id
    res = client.table("shops").insert(row).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Couldn't create the shop.")
    return res.data[0]


@router.patch("/{shop_id}", response_model=ShopOut)
def update_shop(
    shop_id: UUID,
    payload: ShopUpdate,
    user: CurrentUser = Depends(get_current_user),
    client=Depends(get_scoped_client),
):
    """Shop owner (or admin): edit shop details. RLS enforces ownership."""
    row = payload.model_dump(mode="json", exclude_none=True)
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update.")
    res = client.table("shops").update(row).eq("id", str(shop_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found, or you don't have permission to edit it.",
        )
    return res.data[0]


@router.patch("/{shop_id}/status", response_model=ShopOut)
def toggle_open_status(
    shop_id: UUID,
    is_open: bool,
    user: CurrentUser = Depends(get_current_user),
    client=Depends(get_scoped_client),
):
    """Shop owner: flip the open/closed sign for their storefront."""
    res = client.table("shops").update({"is_open": is_open}).eq("id", str(shop_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found, or you don't have permission to edit it.",
        )
    return res.data[0]
