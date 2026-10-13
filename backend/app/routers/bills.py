from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Bill, User
from ..schemas import BillCreateIn, BillPreviewIn
from ..services import bill_service
from ..services.pdf_invoice import build_invoice_pdf

router = APIRouter(prefix="/api/bills", tags=["bills"])


def _get(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found.")
    return bill


@router.post("/preview")
def preview(body: BillPreviewIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Server-side price calculation for the cart. Nothing is saved."""
    return bill_service.preview(db, body)


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: BillCreateIn, response: Response, db: Session = Depends(get_db),
           user: User = Depends(current_user)):
    bill, created = bill_service.create_bill(db, user, body)
    if not created:
        response.status_code = status.HTTP_200_OK  # same idempotency key: original bill returned
    return bill_service.bill_to_dict(bill)


@router.get("")
def list_bills(q: str = Query("", max_length=60), page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
               _: User = Depends(current_user)):
    stmt = select(Bill)
    if q.strip():
        stmt = stmt.where(Bill.bill_number.icontains(q.strip(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Bill.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{k: v for k, v in bill_service.bill_to_dict(b).items() if k not in ("items", "combos")}
             for b in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return bill_service.bill_to_dict(_get(db, bill_id))


@router.get("/{bill_id}/invoice.pdf")
def invoice_pdf(bill_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    data = bill_service.bill_to_dict(_get(db, bill_id))
    pdf = build_invoice_pdf(data, settings.shop_name, settings.shop_address)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{data["bill_number"]}.pdf"'})
