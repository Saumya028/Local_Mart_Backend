from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

OrderStatus = Literal["placed", "confirmed", "packed", "out_for_delivery", "delivered", "cancelled"]

# Valid forward transitions a shop owner can move an order through.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "placed": {"confirmed", "cancelled"},
    "confirmed": {"packed", "cancelled"},
    "packed": {"out_for_delivery", "cancelled"},
    "out_for_delivery": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


class OrderItemIn(BaseModel):
    product_id: UUID
    qty: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    shop_id: UUID
    delivery_address_id: Optional[UUID] = None
    delivery_fee: float = 0
    items: list[OrderItemIn]


class OrderItemOut(BaseModel):
    id: UUID
    product_id: UUID
    product_name_snapshot: str
    unit_price: float
    qty: int
    line_total: float


class OrderOut(BaseModel):
    id: UUID
    customer_id: UUID
    shop_id: UUID
    delivery_address_id: Optional[UUID] = None
    status: OrderStatus
    subtotal: float
    delivery_fee: float
    total: float
    placed_at: datetime
    confirmed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: list[OrderItemOut] = []


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    cancelled_reason: Optional[str] = None
