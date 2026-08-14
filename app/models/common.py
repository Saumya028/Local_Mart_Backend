from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    emoji: Optional[str] = None
    sort_order: int = 0


class AddressCreate(BaseModel):
    label: str = "Home"
    line1: str
    line2: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_default: bool = False


class AddressOut(AddressCreate):
    id: UUID
    customer_id: UUID
    created_at: datetime


class ProfileOut(BaseModel):
    id: UUID
    role: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class DashboardSummaryOut(BaseModel):
    today_revenue: float
    today_orders: int
    yesterday_revenue: float
    yesterday_orders: int
    pending_orders: int


class RevenuePointOut(BaseModel):
    day: date
    revenue: float
    order_count: int


class TopProductOut(BaseModel):
    product_id: UUID
    product_name: str
    qty_sold: int
    revenue: float


class ShopCustomerOut(BaseModel):
    customer_id: UUID
    full_name: Optional[str] = None
    phone: Optional[str] = None
    order_count: int
    total_spent: float
    last_order_at: datetime


class ReviewOut(BaseModel):
    id: UUID
    shop_id: UUID
    customer_id: UUID
    order_id: Optional[UUID] = None
    rating: int
    comment: Optional[str] = None
    created_at: datetime
