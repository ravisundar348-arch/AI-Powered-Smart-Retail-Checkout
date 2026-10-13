from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Bill, Product, User
from ..services import bill_service
from ..services.catalog import product_out

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Real counts only; an empty database yields zeros and empty lists."""
    products = db.scalar(select(func.count()).select_from(Product)) or 0
    active = db.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0
    bills = db.scalar(select(func.count()).select_from(Bill)) or 0
    revenue = db.scalar(select(func.coalesce(func.sum(Bill.total), 0))) or 0
    recent_bills = db.scalars(select(Bill).order_by(Bill.id.desc()).limit(5)).all()
    recent_products = db.scalars(select(Product).order_by(Product.id.desc()).limit(5)).all()
    return {
        "products_total": products, "products_active": active, "bills_total": bills,
        "billed_amount_total": revenue,
        "recent_bills": [{k: v for k, v in bill_service.bill_to_dict(b).items() if k not in ("items", "combos")}
                         for b in recent_bills],
        "recent_products": [product_out(p) for p in recent_products],
    }
