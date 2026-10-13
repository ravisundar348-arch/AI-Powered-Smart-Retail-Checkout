from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import admin_user, current_user
from ..models import BillItem, Product, ProductImage, User
from ..schemas import Page, ProductIn, ProductOut
from ..services.catalog import product_out
from ..services.image_validation import (ImageValidationError, delete_stored_image,
                                         save_product_image)

router = APIRouter(prefix="/api/products", tags=["products"])
MAX_REFERENCE_IMAGES = 10


def _get(db: Session, pid: int) -> Product:
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found.")
    return p


def _check_unique(db: Session, data: ProductIn, exclude_id: int | None = None):
    q = select(Product.id).where(Product.sku == data.sku)
    if exclude_id:
        q = q.where(Product.id != exclude_id)
    if db.scalar(q):
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU '{data.sku}' already exists.")
    if data.barcode:
        q = select(Product.id).where(Product.barcode == data.barcode)
        if exclude_id:
            q = q.where(Product.id != exclude_id)
        if db.scalar(q):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Barcode '{data.barcode}' already exists.")


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "SKU or barcode already exists, or a price rule was violated.")


@router.get("", response_model=Page)
def list_products(q: str = Query("", max_length=100), active: bool | None = None,
                  ai_class: str | None = Query(None, max_length=80),
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), _: User = Depends(current_user)):
    stmt = select(Product)
    if q.strip():
        t = q.strip()
        stmt = stmt.where(or_(Product.name.icontains(t, autoescape=True),
                              Product.sku.icontains(t, autoescape=True),
                              Product.brand.icontains(t, autoescape=True),
                              Product.barcode.icontains(t, autoescape=True)))
    if active is not None:
        stmt = stmt.where(Product.is_active == active)
    if ai_class:
        stmt = stmt.where(Product.ai_class == ai_class)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Product.name, Product.sku)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[product_out(p) for p in rows], total=total, page=page, page_size=page_size)


@router.get("/{pid}", response_model=ProductOut)
def get_product(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return product_out(_get(db, pid))


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    _check_unique(db, data)
    p = Product(**data.model_dump())
    db.add(p)
    _commit(db)
    return product_out(p)


@router.put("/{pid}", response_model=ProductOut)
def update_product(pid: int, data: ProductIn, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    p = _get(db, pid)
    _check_unique(db, data, exclude_id=pid)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    _commit(db)
    return product_out(p)


@router.post("/{pid}/deactivate", response_model=ProductOut)
def deactivate(pid: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    p = _get(db, pid)
    p.is_active = False
    _commit(db)
    return product_out(p)


@router.post("/{pid}/activate", response_model=ProductOut)
def activate(pid: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    p = _get(db, pid)
    p.is_active = True
    _commit(db)
    return product_out(p)


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(pid: int, db: Session = Depends(get_db), _: User = Depends(admin_user)):
    p = _get(db, pid)
    if db.scalar(select(func.count()).select_from(BillItem).where(BillItem.product_id == pid)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This product appears on past bills and cannot be deleted. Deactivate it instead.")
    files = [i.file_name for i in p.images]
    db.delete(p)
    _commit(db)
    for f in files:
        delete_stored_image(settings.product_media_dir, f)


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"Image is too large (limit {settings.max_upload_bytes // (1024 * 1024)} MB).")
    return data


def _store(data: bytes) -> str:
    try:
        return save_product_image(data, settings.product_media_dir,
                                  settings.max_upload_bytes, settings.max_image_pixels)
    except ImageValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("/{pid}/image", response_model=ProductOut)
async def set_primary_image(pid: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                            _: User = Depends(admin_user)):
    p = _get(db, pid)
    name = _store(await _read_upload(file))
    old = [i for i in p.images if i.kind == "primary"]
    for o in old:
        db.delete(o)
    db.add(ProductImage(product_id=p.id, kind="primary", file_name=name))
    _commit(db)
    for o in old:
        delete_stored_image(settings.product_media_dir, o.file_name)
    db.refresh(p)
    return product_out(p)


@router.post("/{pid}/reference-images", response_model=ProductOut)
async def add_reference_image(pid: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                              _: User = Depends(admin_user)):
    """Stores a reference photo. NOTE: the current classifier does NOT use these; they are kept
    for a future enrollment/retraining workflow (see README)."""
    p = _get(db, pid)
    if sum(1 for i in p.images if i.kind == "reference") >= MAX_REFERENCE_IMAGES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"At most {MAX_REFERENCE_IMAGES} reference images per product.")
    name = _store(await _read_upload(file))
    db.add(ProductImage(product_id=p.id, kind="reference", file_name=name))
    _commit(db)
    db.refresh(p)
    return product_out(p)


@router.delete("/{pid}/reference-images/{image_id}", response_model=ProductOut)
def delete_reference_image(pid: int, image_id: int, db: Session = Depends(get_db),
                           _: User = Depends(admin_user)):
    p = _get(db, pid)
    img = next((i for i in p.images if i.id == image_id and i.kind == "reference"), None)
    if not img:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference image not found.")
    name = img.file_name
    db.delete(img)
    _commit(db)
    delete_stored_image(settings.product_media_dir, name)
    db.refresh(p)
    return product_out(p)
