"""API tests (FastAPI TestClient). Run from backend/:  python -m pytest -v"""
import io
import uuid

from PIL import Image


def png(size=(60, 40)):
    b = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(b, "PNG")
    return b.getvalue()


def new_product(client, admin, sku=None, mrp="20.00", price="18.00", **extra):
    sku = sku or f"T-{uuid.uuid4().hex[:8]}".upper()
    body = {"name": f"Prod {sku}", "sku": sku, "mrp": mrp, "selling_price": price, **extra}
    return client.post("/api/products", json=body, headers=admin)


def test_health_and_docs(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/openapi.json").status_code == 200


def test_login_rules(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "ghost", "password": "x"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_admin_endpoints_reject_anonymous_and_cashier(client, cashier):
    body = {"name": "X", "sku": "XX-1", "mrp": "10", "selling_price": "9"}
    assert client.post("/api/products", json=body).status_code == 401
    assert client.post("/api/products", json=body, headers=cashier).status_code == 403


def test_create_edit_and_price_update(client, admin):
    r = new_product(client, admin, sku="edit-me", mrp="50", price="45")
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["sku"] == "EDIT-ME" and p["discount_percent"] == "10.00"
    body = {"name": "Edited", "sku": "EDIT-ME", "mrp": "55", "selling_price": "40", "is_active": True}
    r = client.put(f"/api/products/{p['id']}", json=body, headers=admin)
    assert r.status_code == 200 and r.json()["selling_price"] == "40.00"


def test_duplicate_sku_is_rejected_case_insensitively(client, admin):
    assert new_product(client, admin, sku="DUP-1").status_code == 201
    r = new_product(client, admin, sku="dup-1")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_price_validation(client, admin):
    assert new_product(client, admin, mrp="10", price="12").status_code == 422   # price > MRP
    assert new_product(client, admin, mrp="-1", price="-2").status_code == 422   # negative
    assert new_product(client, admin, mrp="abc", price="1").status_code == 422
    assert new_product(client, admin, sku="a b").status_code == 422              # bad SKU


def test_listing_and_search(client, admin, cashier):
    new_product(client, admin, sku="SEARCHABLE-777")
    r = client.get("/api/products", params={"q": "searchable-777"}, headers=cashier)
    assert r.status_code == 200 and r.json()["total"] == 1
    assert client.get("/api/products", params={"page_size": 1000}, headers=cashier).status_code == 422


def test_image_upload_validation(client, admin):
    pid = new_product(client, admin).json()["id"]
    ok = client.post(f"/api/products/{pid}/image", files={"file": ("a.png", png(), "image/png")}, headers=admin)
    assert ok.status_code == 200 and ok.json()["image_url"].startswith("/media/products/")
    assert client.get(ok.json()["image_url"]).status_code == 200
    bad = client.post(f"/api/products/{pid}/image", files={"file": ("a.png", b"<html>", "image/png")}, headers=admin)
    assert bad.status_code == 422


def test_billing_uses_server_prices_and_persists_snapshot(client, admin, cashier):
    p = new_product(client, admin, mrp="100", price="80").json()
    items = [{"product_id": p["id"], "quantity": 3, "unit_price": "1"}]  # client price must be ignored
    pre = client.post("/api/bills/preview", json={"items": items}, headers=cashier).json()
    assert float(pre["total"]) == 240.0
    key = uuid.uuid4().hex
    r = client.post("/api/bills", json={"idempotency_key": key, "items": items}, headers=cashier)
    assert r.status_code == 201, r.text
    bill = r.json()
    assert float(bill["total"]) == 240.0 and bill["bill_number"].startswith("INV-")
    # idempotent resubmission returns the same bill
    again = client.post("/api/bills", json={"idempotency_key": key, "items": items}, headers=cashier)
    assert again.status_code == 200 and again.json()["id"] == bill["id"]
    # price change must not rewrite the history
    body = {"name": p["name"], "sku": p["sku"], "mrp": "100", "selling_price": "10"}
    assert client.put(f"/api/products/{p['id']}", json=body, headers=admin).status_code == 200
    saved = client.get(f"/api/bills/{bill['id']}", headers=cashier).json()
    assert float(saved["total"]) == 240.0 and float(saved["items"][0]["unit_price"]) == 80.0


def test_quantity_validation_and_unknown_product(client, admin, cashier):
    p = new_product(client, admin).json()
    for q in (0, -1, 100000):
        r = client.post("/api/bills/preview", json={"items": [{"product_id": p["id"], "quantity": q}]}, headers=cashier)
        assert r.status_code == 422
    r = client.post("/api/bills/preview", json={"items": [{"product_id": 999999, "quantity": 1}]}, headers=cashier)
    assert r.status_code == 422


def test_inactive_product_cannot_be_billed_and_used_product_cannot_be_deleted(client, admin, cashier):
    p = new_product(client, admin).json()
    bill = client.post("/api/bills", json={"idempotency_key": uuid.uuid4().hex,
                                           "items": [{"product_id": p["id"], "quantity": 1}]}, headers=cashier)
    assert bill.status_code == 201
    assert client.delete(f"/api/products/{p['id']}", headers=admin).status_code == 409
    assert client.post(f"/api/products/{p['id']}/deactivate", headers=admin).json()["is_active"] is False
    r = client.post("/api/bills/preview", json={"items": [{"product_id": p["id"], "quantity": 1}]}, headers=cashier)
    assert r.status_code == 409
    unused = new_product(client, admin).json()
    assert client.delete(f"/api/products/{unused['id']}", headers=admin).status_code == 204


def test_invoice_pdf_and_history(client, admin, cashier):
    p = new_product(client, admin).json()
    bill = client.post("/api/bills", json={"idempotency_key": uuid.uuid4().hex,
                                           "items": [{"product_id": p["id"], "quantity": 2}]}, headers=cashier).json()
    pdf = client.get(f"/api/bills/{bill['id']}/invoice.pdf", headers=cashier)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/bills/{bill['id']}/invoice.pdf").status_code == 401
    hist = client.get("/api/bills", params={"q": bill["bill_number"]}, headers=cashier).json()
    assert hist["total"] == 1
    assert client.get("/api/bills/99999999", headers=cashier).status_code == 404


def test_scan_without_models_is_honest(client, cashier):
    r = client.post("/api/scan", files={"file": ("s.png", png(), "image/png")}, headers=cashier)
    assert r.status_code == 200
    body = r.json()
    assert body["ai_available"] is False and body["detections"] == [] and body["reason"]
    bad = client.post("/api/scan", files={"file": ("s.png", b"junk", "image/png")}, headers=cashier)
    assert bad.status_code == 422


def test_dashboard_has_real_counts(client, cashier):
    d = client.get("/api/dashboard", headers=cashier).json()
    assert d["products_total"] >= 1 and "recent_bills" in d
