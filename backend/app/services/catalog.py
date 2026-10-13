from decimal import Decimal

from ..models import Product
from ..schemas import ProductImageOut, ProductOut
from .billing import money

MEDIA_PREFIX = "/media/products/"


def product_out(p: Product) -> ProductOut:
    mrp, price = money(p.mrp), money(p.selling_price)
    disc = mrp - price
    pct = money(disc / mrp * 100) if mrp > 0 else Decimal("0.00")
    primary = next((i for i in p.images if i.kind == "primary"), None)
    refs = [ProductImageOut(id=i.id, kind=i.kind, url=MEDIA_PREFIX + i.file_name)
            for i in p.images if i.kind == "reference"]
    return ProductOut(
        id=p.id, sku=p.sku, name=p.name, brand=p.brand, category=p.category, variant=p.variant,
        pack_size=p.pack_size, unit=p.unit, barcode=p.barcode, mrp=mrp, selling_price=price,
        discount_amount=disc, discount_percent=pct, ai_class=p.ai_class, is_active=p.is_active,
        image_url=(MEDIA_PREFIX + primary.file_name) if primary else None,
        reference_images=refs, created_at=p.created_at,
    )


def pack_label(p: Product) -> str:
    return " ".join(x for x in (p.pack_size, p.unit) if x).strip()
