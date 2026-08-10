from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class DealCreate(BaseModel):
    product_id: Optional[UUID] = None
    title: str
    discount_type: Literal["percentage", "flat", "bogo"]
    discount_value: float = 0
    starts_at: Optional[datetime] = None
    ends_at: datetime


class DealOut(BaseModel):
    id: UUID
    shop_id: UUID
    product_id: Optional[UUID] = None
    title: str
    discount_type: str
    discount_value: float
    starts_at: datetime
    ends_at: datetime
    is_active: bool
