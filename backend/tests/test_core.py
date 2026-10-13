"""Tests for the dependency-light core (billing, security, images, AI post-processing, PDF).

Run with:  python -m unittest discover -s tests -p "test_core.py" -v
"""
import io
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import numpy as np
from PIL import Image

from app import security
from app.services import ai_postprocess as pp
from app.services import billing as b
from app.services import image_validation as iv
from app.services.offers import load_offers
from app.services.pdf_invoice import build_invoice_pdf


def line(pid, sku, qty, price, mrp=None):
    return b.CartLine(pid, sku, sku.title(), qty, D(mrp or price), D(price))


class BillingTests(unittest.TestCase):
    def test_line_total_and_subtotal(self):
        c = b.price_cart([line(1, "A", 3, "10.00"), line(2, "B", 2, "250.50")])
        self.assertEqual(c.subtotal, D("531.00"))
        self.assertEqual(c.total, D("531.00"))
        self.assertEqual(c.item_count, 5)

    def test_duplicate_products_merge(self):
        c = b.price_cart([line(1, "A", 1, "10"), line(1, "A", 4, "10")])
        self.assertEqual(len(c.lines), 1)
        self.assertEqual(c.lines[0].quantity, 5)
        self.assertEqual(c.total, D("50.00"))

    def test_festival_applies_once_rounded_per_unit(self):
        f = b.FestivalOffer("Test", date(2026, 1, 1), date(2026, 1, 2), D(25))
        c = b.price_cart([line(1, "A", 3, "33.33")], festival=f)
        # unit = round(33.33 * .75, 2) = 24.9975 -> 25.00 ; 3 * 25.00
        self.assertEqual(c.lines[0].effective_unit_price, D("25.00"))
        self.assertEqual(c.total, D("75.00"))
        self.assertEqual(c.festival_discount, D("99.99") - D("75.00"))
        self.assertEqual(c.subtotal - c.festival_discount, c.total)

    def test_best_single_festival_not_compounded(self):
        offers = [
            b.FestivalOffer("Ten", date(2026, 5, 1), date(2026, 5, 3), D(10)),
            b.FestivalOffer("Twenty", date(2026, 5, 2), date(2026, 5, 4), D(20)),
        ]
        best = b.best_active_festival(offers, date(2026, 5, 2))
        self.assertEqual(best.name, "Twenty")
        self.assertIsNone(b.best_active_festival(offers, date(2026, 6, 1)))

    def test_combo_complete_sets_only_and_no_double_use(self):
        combo = b.ComboOffer("Snack", ("A", "B"), D(10))
        other = b.ComboOffer("Other", ("A", "C"), D(50))
        c = b.price_cart([line(1, "A", 3, "100"), line(2, "B", 2, "50"), line(3, "C", 5, "10")],
                         combos=[combo, other])
        # Snack: 2 sets of (100+50)=300 -> 30 off. A has 1 left; Other: 1 set of (100+10)=110 -> 55 off.
        self.assertEqual([x.name for x in c.combos], ["Snack", "Other"])
        self.assertEqual(c.combos[0].sets, 2)
        self.assertEqual(c.combos[0].discount_amount, D("30.00"))
        self.assertEqual(c.combos[1].sets, 1)
        self.assertEqual(c.combos[1].discount_amount, D("55.00"))
        self.assertEqual(c.subtotal, D("450.00"))  # 300 + 100 + 50
        self.assertEqual(c.total, D("365.00"))     # 450 - 30 - 55

    def test_combo_incomplete_not_applied(self):
        combo = b.ComboOffer("Snack", ("A", "B"), D(10))
        c = b.price_cart([line(1, "A", 2, "100")], combos=[combo])
        self.assertEqual(c.combos, [])
        self.assertEqual(c.total, D("200.00"))

    def test_combo_stacks_on_festival_price(self):
        f = b.FestivalOffer("F", date(2026, 1, 1), date(2026, 1, 1), D(10))
        combo = b.ComboOffer("C", ("A", "B"), D(10))
        c = b.price_cart([line(1, "A", 1, "100"), line(2, "B", 1, "100")], festival=f, combos=[combo])
        # festival unit 90 each => 180 ; combo 10% of 180 = 18 => 162
        self.assertEqual(c.total, D("162.00"))

    def test_validation(self):
        with self.assertRaises(b.BillingError):
            b.price_cart([])
        with self.assertRaises(b.BillingError):
            b.price_cart([line(1, "A", 0, "10")])
        with self.assertRaises(b.BillingError):
            b.price_cart([line(1, "A", 1, "-1")])

    def test_decimal_safety(self):
        c = b.price_cart([line(1, "A", 3, "0.10")])
        self.assertEqual(c.total, D("0.30"))  # float would give 0.30000000000000004

    def test_offers_file_loads(self):
        festivals, combos = load_offers()
        self.assertEqual(len(festivals), 9)
        self.assertEqual(len(combos), 3)
        self.assertEqual(combos[2].skus, ("HNS-SHAMPOO", "PLUM", "CERAVE"))


class SecurityTests(unittest.TestCase):
    def test_hash_roundtrip(self):
        h = security.hash_password("correct horse")
        self.assertNotIn("correct horse", h)
        self.assertTrue(security.verify_password("correct horse", h))
        self.assertFalse(security.verify_password("wrong", h))
        self.assertNotEqual(h, security.hash_password("correct horse"))  # unique salt

    def test_bad_hash_is_false(self):
        self.assertFalse(security.verify_password("x", "not-a-hash"))

    def test_jwt(self):
        t = security.create_access_token(7, "admin")
        data = security.decode_access_token(t)
        self.assertEqual((data["sub"], data["role"]), ("7", "admin"))
        self.assertIsNone(security.decode_access_token(t + "x"))
        self.assertIsNone(security.decode_access_token("garbage"))


def png_bytes(size=(64, 48), mode="RGB", fmt="PNG"):
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(buf, fmt)
    return buf.getvalue()


class ImageTests(unittest.TestCase):
    def test_valid_png(self):
        img = iv.load_image(png_bytes(), 1_000_000, 10_000_000)
        self.assertEqual(img.size, (64, 48))
        self.assertEqual(img.mode, "RGB")

    def test_rgba_flattened(self):
        img = iv.load_image(png_bytes(mode="RGBA"), 1_000_000, 10_000_000)
        self.assertEqual(img.mode, "RGB")

    def test_rejects_garbage_empty_big_and_wrong_type(self):
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(b"not an image", 1000, 10**7)
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(b"", 1000, 10**7)
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(png_bytes((300, 300)), 100, 10**7)
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(png_bytes((300, 300)), 10**6, 1000)  # too many pixels
        gif = io.BytesIO()
        Image.new("RGB", (8, 8)).save(gif, "GIF")
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(gif.getvalue(), 10**6, 10**7)

    def test_rejects_html_disguised_as_image(self):
        with self.assertRaises(iv.ImageValidationError):
            iv.load_image(b"<html><script>alert(1)</script></html>", 10**6, 10**7)

    def test_save_uses_random_name_and_jpeg(self):
        with tempfile.TemporaryDirectory() as d:
            name = iv.save_product_image(png_bytes((3000, 2000)), Path(d), 10**7, 10**8)
            self.assertRegex(name, r"^[0-9a-f]{32}\.jpg$")
            with Image.open(Path(d) / name) as saved:
                self.assertEqual(saved.format, "JPEG")
                self.assertLessEqual(max(saved.size), 1600)

    def test_delete_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            outside = Path(d) / "outside.txt"
            outside.write_text("keep")
            inner = Path(d) / "inner"
            inner.mkdir()
            iv.delete_stored_image(inner, "../outside.txt")
            self.assertTrue(outside.exists())


class PostprocessTests(unittest.TestCase):
    def test_iou(self):
        self.assertAlmostEqual(pp.calculate_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertEqual(pp.calculate_iou((0, 0, 10, 10), (20, 20, 30, 30)), 0.0)
        self.assertEqual(pp.calculate_iou((0, 0, 0, 0), (0, 0, 0, 0)), 0.0)  # no ZeroDivisionError

    def test_remove_nested_original_logic(self):
        dets = [{"bbox": (0, 0, 100, 100)}, {"bbox": (2, 2, 98, 98)}, {"bbox": (200, 200, 300, 300)}]
        kept = pp.remove_nested_boxes(dets)
        self.assertEqual(len(kept), 2)
        self.assertNotIn((2, 2, 98, 98), [d["bbox"] for d in kept])

    def test_contained_box_addition(self):
        dets = [{"bbox": (0, 0, 100, 100)}, {"bbox": (40, 40, 60, 60)}, {"bbox": (150, 0, 250, 100)}]
        self.assertEqual(len(pp.remove_nested_boxes(dets)), 3)      # IoU alone misses it
        self.assertEqual(len(pp.remove_contained_boxes(dets)), 2)   # containment catches it

    def test_square_padding_and_crop(self):
        img = np.zeros((50, 100, 3), dtype=np.uint8)
        sq = pp.make_square_with_padding(img)
        self.assertEqual(sq.shape, (100, 100, 3))
        self.assertTrue((sq[0, 0] == 255).all())
        full = np.zeros((200, 300, 3), dtype=np.uint8)
        out = pp.prepare_crop(full, (-20, -20, 150, 120))
        self.assertEqual(out.shape, (224, 224, 3))
        self.assertIsNone(pp.prepare_crop(full, (10, 10, 12, 12)))


class PdfTests(unittest.TestCase):
    def test_invoice_pdf_generates(self):
        bill = {
            "bill_number": "INV-20261009-00001", "created_display": "09 Oct 2026, 10:30", "status": "FINALIZED",
            "items": [{"name": "Thums Up <script>", "sku": "THUMS-UP", "pack": "750 ml", "quantity": 2,
                       "unit_mrp": "20.00", "unit_price": "20.00", "festival_discount": "0.00",
                       "line_total": "40.00"}],
            "subtotal": "40.00", "festival_discount": "0.00", "festival_name": None, "festival_percent": "0",
            "combos": [{"name": "Snack Combo", "sets": 1, "discount_percent": "3", "discount_amount": "1.20"}],
            "total": "38.80",
        }
        pdf = build_invoice_pdf(bill, "Test Shop & Co", "1 Main St")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1500)


if __name__ == "__main__":
    unittest.main()
