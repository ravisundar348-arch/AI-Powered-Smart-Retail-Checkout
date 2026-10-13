import re
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Decimal
SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,63}$")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=2, max_length=64)
    brand: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=80)
    variant: str = Field(default="", max_length=80)
    pack_size: str = Field(default="", max_length=30)
    unit: str = Field(default="", max_length=20)
    barcode: Optional[str] = Field(default=None, max_length=64)
    mrp: Money = Field(ge=0, max_digits=10, decimal_places=2)
    selling_price: Money = Field(ge=0, max_digits=10, decimal_places=2)
    ai_class: Optional[str] = Field(default=None, max_length=80)
    is_active: bool = True

    @field_validator("name", "brand", "category", "variant", "pack_size", "unit", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("sku", mode="before")
    @classmethod
    def _sku(cls, v):
        v = (v or "").strip().upper() if isinstance(v, str) else v
        if not isinstance(v, str) or not SKU_RE.match(v):
            raise ValueError("SKU must be 2-64 characters: letters, digits, '.', '_' or '-'.")
        return v

    @field_validator("barcode", "ai_class", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @model_validator(mode="after")
    def _prices(self):
        if self.selling_price > self.mrp:
            raise ValueError("Selling price cannot be higher than MRP.")
        return self


class ProductImageOut(BaseModel):
    id: int
    kind: str
    url: str


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    brand: str
    category: str
    variant: str
    pack_size: str
    unit: str
    barcode: Optional[str]
    mrp: Money
    selling_price: Money
    discount_amount: Money
    discount_percent: Money
    ai_class: Optional[str]
    is_active: bool
    image_url: Optional[str]
    reference_images: list[ProductImageOut] = []
    created_at: datetime


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class CartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=999)
    source: Literal["ai", "manual"] = "manual"
    ai_class: Optional[str] = Field(default=None, max_length=80)
    ai_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class BillPreviewIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=200)


class BillCreateIn(BillPreviewIn):
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
