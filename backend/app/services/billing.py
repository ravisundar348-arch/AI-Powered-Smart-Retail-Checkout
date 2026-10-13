"""Pure billing engine (no database / web imports) so it is easy to test.

Rules (ported from Detect_Classify_Bill.ipynb, with the double-discount
hazards removed):

1. Unit price = the product's *selling price* from the catalog.
2. At most ONE festival offer applies (the largest active one). The original
   notebook compounded every overlapping festival; that is not done here.
   The festival price is rounded per unit, as in the notebook.
3. Combo offers apply to complete sets, computed on the festival-adjusted
   unit price (the notebook also stacked combo on festival). A unit of stock
   can belong to only one combo, so no unit is discounted twice by combos.
4. All arithmetic is Decimal, rounded half-up to 2 places.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class BillingError(ValueError):
    pass


@dataclass(frozen=True)
class CartLine:
    product_id: int
    sku: str
    name: str
    quantity: int
    unit_mrp: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class FestivalOffer:
    name: str
    start_date: date
    end_date: date
    discount_percent: Decimal

    def is_active(self, today: date) -> bool:
        return self.start_date <= today <= self.end_date


@dataclass(frozen=True)
class ComboOffer:
    name: str
    skus: tuple
    discount_percent: Decimal


@dataclass
class PricedLine:
    product_id: int
    sku: str
    name: str
    quantity: int
    unit_mrp: Decimal
    unit_price: Decimal           # catalog selling price
    effective_unit_price: Decimal  # after festival offer
    gross: Decimal                # quantity * unit_price
    festival_discount: Decimal
    line_total: Decimal           # quantity * effective_unit_price (before combos)


@dataclass
class AppliedCombo:
    name: str
    sets: int
    discount_percent: Decimal
    base_amount: Decimal
    discount_amount: Decimal


@dataclass
class BillCalculation:
    lines: list = field(default_factory=list)
    combos: list = field(default_factory=list)
    festival_name: str | None = None
    festival_percent: Decimal = Decimal(0)
    mrp_total: Decimal = Decimal(0)
    subtotal: Decimal = Decimal(0)
    festival_discount: Decimal = Decimal(0)
    combo_discount: Decimal = Decimal(0)
    total: Decimal = Decimal(0)
    item_count: int = 0


def merge_lines(lines: Iterable[CartLine]) -> list:
    """Combine duplicate products into one line (quantities add up)."""
    merged: dict = {}
    for ln in lines:
        if ln.product_id in merged:
            prev = merged[ln.product_id]
            merged[ln.product_id] = CartLine(
                prev.product_id, prev.sku, prev.name, prev.quantity + ln.quantity,
                prev.unit_mrp, prev.unit_price,
            )
        else:
            merged[ln.product_id] = ln
    return list(merged.values())


def best_active_festival(offers: Iterable[FestivalOffer], today: date) -> FestivalOffer | None:
    active = [o for o in offers if o.is_active(today)]
    return max(active, key=lambda o: o.discount_percent) if active else None


def price_cart(
    lines: Iterable[CartLine],
    festival: FestivalOffer | None = None,
    combos: Iterable[ComboOffer] = (),
) -> BillCalculation:
    cart = merge_lines(lines)
    if not cart:
        raise BillingError("The cart is empty.")

    calc = BillCalculation()
    pct = Decimal(festival.discount_percent) if festival else Decimal(0)
    if pct < 0 or pct > 100:
        raise BillingError("Festival discount must be between 0 and 100.")
    if festival and pct > 0:
        calc.festival_name, calc.festival_percent = festival.name, pct

    effective_by_sku: dict = {}
    for ln in cart:
        if not isinstance(ln.quantity, int) or ln.quantity < 1:
            raise BillingError(f"Invalid quantity for {ln.sku}.")
        if ln.unit_price < 0 or ln.unit_mrp < 0:
            raise BillingError(f"Invalid price for {ln.sku}.")
        unit = money(ln.unit_price)
        effective = money(unit * (HUNDRED - pct) / HUNDRED) if pct > 0 else unit
        gross = unit * ln.quantity
        line_total = effective * ln.quantity
        calc.lines.append(PricedLine(
            ln.product_id, ln.sku, ln.name, ln.quantity, money(ln.unit_mrp), unit,
            effective, gross, gross - line_total, line_total,
        ))
        effective_by_sku[ln.sku] = effective
        calc.mrp_total += money(ln.unit_mrp) * ln.quantity
        calc.subtotal += gross
        calc.festival_discount += gross - line_total
        calc.item_count += ln.quantity

    remaining = {ln.sku: ln.quantity for ln in cart}
    for combo in combos:
        skus = tuple(combo.skus)
        cpct = Decimal(combo.discount_percent)
        if len(skus) < 2 or len(set(skus)) != len(skus) or cpct <= 0 or cpct > 100:
            continue
        if not all(remaining.get(s, 0) > 0 for s in skus):
            continue
        sets = min(remaining[s] for s in skus)
        base = sum((effective_by_sku[s] * sets for s in skus), Decimal(0))
        discount = money(base * cpct / HUNDRED)
        for s in skus:
            remaining[s] -= sets
        calc.combos.append(AppliedCombo(combo.name, sets, cpct, base, discount))
        calc.combo_discount += discount

    calc.total = calc.subtotal - calc.festival_discount - calc.combo_discount
    if calc.total < 0:
        raise BillingError("Bill total cannot be negative.")
    return calc


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
