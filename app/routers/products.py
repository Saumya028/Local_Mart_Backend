from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_scoped_client
from app.core.supabase import get_anon_client
from app.models.product import ProductCreate, ProductOut, ProductUpdate, StockUpdate

router = APIRouter(tags=["products"])


@router.get("/shops/{shop_id}/products", response_model=list[ProductOut])
def list_shop_products(
    shop_id: UUID,
    category_id: Optional[UUID] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """Public: a shop's active catalog — this is the shop's page on LocalMart."""
    client = get_anon_client()
    query = (
        client.table("products")
        .select("*")
        .eq("shop_id", str(shop_id))
        .eq("is_active", True)
    )
    if category_id:
        query = query.eq("category_id", str(category_id))
    if q:
        query = query.ilike("name", f"%{q}%")
    res = query.range(offset, offset + limit - 1).execute()
    return res.data


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID):
    """Public: single product detail."""
    client = get_anon_client()
    res = client.table("products").select("*").eq("id", str(product_id)).single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return res.data


@router.get("/products", response_model=list[ProductOut])
def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, le=100),
):
    """Public: search products across every shop — the Amazon-style search bar."""
    client = get_anon_client()
    res = (
        client.table("products")
        .select("*")
        .eq("is_active", True)
        .ilike("name", f"%{q}%")
        .limit(limit)
        .execute()
    )
    return res.data


@router.post("/shops/{shop_id}/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(shop_id: UUID, payload: ProductCreate, client=Depends(get_scoped_client)):
    """Shop owner: add a new item to their inventory."""
    row = payload.model_dump(mode="json", exclude_none=True)
    row["shop_id"] = str(shop_id)
    res = client.table("products").insert(row).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couldn't add the product — check that you own this shop.",
        )
    return res.data[0]


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: UUID, payload: ProductUpdate, client=Depends(get_scoped_client)):
    """Shop owner: edit a product's details."""
    row = payload.model_dump(mode="json", exclude_none=True)
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update.")
    res = client.table("products").update(row).eq("id", str(product_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found, or you don't have permission to edit it.",
        )
    return res.data[0]


@router.patch("/products/{product_id}/stock", response_model=ProductOut)
def update_stock(product_id: UUID, payload: StockUpdate, client=Depends(get_scoped_client)):
    """Shop owner: quick inventory-count update (restocks, corrections)."""
    res = (
        client.table("products")
        .update({"stock_qty": payload.stock_qty})
        .eq("id", str(product_id))
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found, or you don't have permission to edit it.",
        )
    return res.data[0]


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: UUID, client=Depends(get_scoped_client)):
    """Shop owner: remove a product from the catalog."""
    res = client.table("products").delete().eq("id", str(product_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found, or you don't have permission to delete it.",
        )
