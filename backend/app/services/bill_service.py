"""Bridges the database and the pure billing engine."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Bill, BillCombo, BillItem, Product, User
from ..schemas import BillCreateIn, BillPreviewIn
from . import billing
from .catalog import pack_label
from .offers import load_offers


def _tz():
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def shop_today():
    return datetime.now(_tz()).date()


def _price(db: Session, payload: BillPreviewIn):
    """Fetch authoritative prices from the catalog. Client-supplied prices are never read."""
    ids = {i.product_id for i in payload.items}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)))}
    missing = sorted(ids - products.keys())
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown product id(s): {missing}")
    inactive = [p.sku for p in products.values() if not p.is_active]
    if inactive:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Inactive product(s) cannot be billed: {', '.join(sorted(inactive))}")
    lines = [billing.CartLine(p.id, p.sku, p.name, 0, p.mrp, p.selling_price) for p in products.values()]
    qty: dict = {}
    for it in payload.items:
        qty[it.product_id] = qty.get(it.product_id, 0) + it.quantity
    lines = [billing.CartLine(l.product_id, l.sku, l.name, qty[l.product_id], l.unit_mrp, l.unit_price)
             for l in lines]
    if any(q > 9999 for q in qty.values()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Quantity is too large.")
    festivals, combos = load_offers()
    festival = billing.best_active_festival(festivals, shop_today())
    try:
        calc = billing.price_cart(lines, festival, combos)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return calc, products


def preview(db: Session, payload: BillPreviewIn) -> dict:
    calc, _ = _price(db, payload)
    return calc_to_dict(calc)


def calc_to_dict(calc: billing.BillCalculation) -> dict:
    return {
        "lines": [{
            "product_id": l.product_id, "sku": l.sku, "name": l.name, "quantity": l.quantity,
            "unit_mrp": l.unit_mrp, "unit_price": l.unit_price,
            "effective_unit_price": l.effective_unit_price,
            "festival_discount": l.festival_discount, "line_total": l.line_total,
        } for l in calc.lines],
        "combos": [{"name": c.name, "sets": c.sets, "discount_percent": c.discount_percent,
                    "base_amount": c.base_amount, "discount_amount": c.discount_amount} for c in calc.combos],
        "festival_name": calc.festival_name, "festival_percent": calc.festival_percent,
        "mrp_total": calc.mrp_total, "subtotal": calc.subtotal,
        "festival_discount": calc.festival_discount, "combo_discount": calc.combo_discount,
        "total": calc.total, "item_count": calc.item_count,
    }


def create_bill(db: Session, user: User, payload: BillCreateIn) -> tuple[Bill, bool]:
    """Returns (bill, created). A repeated idempotency key returns the original bill."""
    existing = db.scalar(select(Bill).where(Bill.idempotency_key == payload.idempotency_key))
    if existing:
        return existing, False

    calc, products = _price(db, payload)
    meta = {}
    for it in payload.items:  # first occurrence of a product keeps its AI metadata
        meta.setdefault(it.product_id, it)

    bill = Bill(
        idempotency_key=payload.idempotency_key, created_by=user.id, status="FINALIZED",
        item_count=calc.item_count, mrp_total=calc.mrp_total, subtotal=calc.subtotal,
        festival_name=calc.festival_name, festival_percent=calc.festival_percent,
        festival_discount=calc.festival_discount, combo_discount=calc.combo_discount, total=calc.total,
    )
    for l in calc.lines:
        p, m = products[l.product_id], meta[l.product_id]
        bill.items.append(BillItem(
            product_id=p.id, sku=p.sku, name=p.name, pack=pack_label(p), quantity=l.quantity,
            unit_mrp=l.unit_mrp, unit_price=l.unit_price, effective_unit_price=l.effective_unit_price,
            festival_discount=l.festival_discount, line_total=l.line_total,
            source=m.source, ai_class=m.ai_class if m.source == "ai" else None,
            ai_confidence=Decimal(str(m.ai_confidence)) if (m.source == "ai" and m.ai_confidence is not None) else None,
        ))
    for c in calc.combos:
        bill.combos.append(BillCombo(name=c.name, sets=c.sets, discount_percent=c.discount_percent,
                                     base_amount=c.base_amount, discount_amount=c.discount_amount))
    try:
        db.add(bill)
        db.flush()
        bill.bill_number = f"INV-{datetime.now(_tz()):%Y%m%d}-{bill.id:05d}"
        db.commit()
    except IntegrityError:
        db.rollback()
        again = db.scalar(select(Bill).where(Bill.idempotency_key == payload.idempotency_key))
        if again:
            return again, False
        raise HTTPException(status.HTTP_409_CONFLICT, "Could not save the bill. Please try again.")
    return bill, True


def bill_to_dict(bill: Bill) -> dict:
    local = bill.created_at
    if local.tzinfo is None:  # SQLite returns naive UTC
        from datetime import timezone
        local = local.replace(tzinfo=timezone.utc)
    local = local.astimezone(_tz())
    return {
        "id": bill.id, "bill_number": bill.bill_number, "status": bill.status,
        "created_at": bill.created_at.isoformat() if bill.created_at else None,
        "created_display": local.strftime("%d %b %Y, %I:%M %p"),
        "item_count": bill.item_count, "mrp_total": bill.mrp_total, "subtotal": bill.subtotal,
        "festival_name": bill.festival_name, "festival_percent": bill.festival_percent,
        "festival_discount": bill.festival_discount, "combo_discount": bill.combo_discount,
        "total": bill.total,
        "items": [{
            "sku": i.sku, "name": i.name, "pack": i.pack, "quantity": i.quantity,
            "unit_mrp": i.unit_mrp, "unit_price": i.unit_price,
            "effective_unit_price": i.effective_unit_price,
            "festival_discount": i.festival_discount, "line_total": i.line_total,
            "source": i.source, "ai_class": i.ai_class,
            "ai_confidence": i.ai_confidence,
        } for i in bill.items],
        "combos": [{"name": c.name, "sets": c.sets, "discount_percent": c.discount_percent,
                    "base_amount": c.base_amount, "discount_amount": c.discount_amount} for c in bill.combos],
    }
