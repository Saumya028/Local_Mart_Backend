from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    sku: Optional[str] = None
    price: float = Field(..., ge=0)
    mrp: Optional[float] = Field(None, ge=0)
    stock_qty: int = Field(0, ge=0)
    image_url: Optional[str] = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    sku: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    mrp: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class StockUpdate(BaseModel):
    stock_qty: int = Field(..., ge=0)


class ProductOut(BaseModel):
    id: UUID
    shop_id: UUID
    category_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    sku: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    stock_qty: int
    image_url: Optional[str] = None
    is_active: bool
    created_at: datetime
