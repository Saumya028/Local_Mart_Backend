from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ShopCreate(BaseModel):
    name: str
    slug: str
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    delivery_radius_km: float = 3
    avg_delivery_minutes: int = 25


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_open: Optional[bool] = None
    delivery_radius_km: Optional[float] = None
    avg_delivery_minutes: Optional[int] = None


class ShopOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    slug: str
    category_id: Optional[UUID] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_open: bool
    is_verified: bool
    rating: float
    rating_count: int
    delivery_radius_km: float
    avg_delivery_minutes: int
    created_at: datetime


class NearbyShopOut(BaseModel):
    id: UUID
    name: str
    slug: str
    category_id: Optional[UUID] = None
    logo_url: Optional[str] = None
    rating: float
    rating_count: int
    is_open: bool
    avg_delivery_minutes: int
    distance_km: float = Field(..., description="Great-circle distance from the query point, in km")
