from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import CurrentUser, get_current_user, get_scoped_client
from app.models.order import ALLOWED_TRANSITIONS, OrderCreate, OrderOut, OrderStatus, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])

# order_items is fetched as an embedded resource via PostgREST's FK-based join.
_ORDER_SELECT = "*, order_items(*)"


@router.get("", response_model=list[OrderOut])
def list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    shop_id: Optional[UUID] = None,
    client=Depends(get_scoped_client),
):
    """
    Orders visible to the caller: a customer sees their own order history,
    a shop owner sees the order queue for their shop(s) — RLS decides which.
    """
    query = client.table("orders").select(_ORDER_SELECT)
    if status_filter:
        query = query.eq("status", status_filter)
    if shop_id:
        query = query.eq("shop_id", str(shop_id))
    res = query.order("placed_at", desc=True).execute()
    return res.data


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: UUID, client=Depends(get_scoped_client)):
    res = client.table("orders").select(_ORDER_SELECT).eq("id", str(order_id)).single().execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return res.data


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def place_order(
    payload: OrderCreate,
    user: CurrentUser = Depends(get_current_user),
    client=Depends(get_scoped_client),
):
    """
    Place an order. Delegates to the create_order() Postgres function so
    stock validation, stock decrement, and order+item writes happen in one
    transaction — two customers can't oversell the same last unit.
    """
    rpc_res = client.rpc(
        "create_order",
        {
            "p_shop_id": str(payload.shop_id),
            "p_delivery_address_id": str(payload.delivery_address_id) if payload.delivery_address_id else None,
            "p_items": [item.model_dump(mode="json") for item in payload.items],
            "p_delivery_fee": payload.delivery_fee,
        },
    ).execute()

    if not rpc_res.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Couldn't place the order.")

    order_id = rpc_res.data
    order_res = client.table("orders").select(_ORDER_SELECT).eq("id", order_id).single().execute()
    return order_res.data


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: UUID, payload: OrderStatusUpdate, client=Depends(get_scoped_client)):
    """
    Shop owner: move an order forward (confirmed → packed → out_for_delivery
    → delivered), or cancel it. Enforces the valid state machine before
    writing; RLS separately enforces that only the owning shop can do this.
    """
    current = client.table("orders").select("status").eq("id", str(order_id)).single().execute()
    if not current.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    current_status = current.data["status"]
    if payload.status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can't move an order from '{current_status}' to '{payload.status}'.",
        )

    now = datetime.now(timezone.utc).isoformat()
    update_row: dict = {"status": payload.status}
    if payload.status == "confirmed":
        update_row["confirmed_at"] = now
    if payload.status == "delivered":
        update_row["delivered_at"] = now
    if payload.status == "cancelled" and payload.cancelled_reason:
        update_row["cancelled_reason"] = payload.cancelled_reason

    res = client.table("orders").update(update_row).eq("id", str(order_id)).execute()
    order_res = client.table("orders").select(_ORDER_SELECT).eq("id", str(order_id)).single().execute()
    return order_res.data
