"""Invoice PDF generation with ReportLab. Works on plain dicts (no ORM)."""
import io
import os
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]
_RUPEE = "\u20b9"
_font_state: dict = {}


def _fonts():
    """Pick a TTF containing the rupee glyph; otherwise fall back to Helvetica + 'Rs.'."""
    if _font_state:
        return _font_state["regular"], _font_state["bold"], _font_state["symbol"]
    for reg, bold in _FONT_CANDIDATES:
        if os.path.isfile(reg) and os.path.isfile(bold):
            try:
                font = TTFont("InvRegular", reg)
                if ord(_RUPEE) not in font.face.charToGlyph:
                    continue
                pdfmetrics.registerFont(font)
                pdfmetrics.registerFont(TTFont("InvBold", bold))
                _font_state.update(regular="InvRegular", bold="InvBold", symbol=_RUPEE)
                return "InvRegular", "InvBold", _RUPEE
            except Exception:  # noqa: BLE001 - try next candidate
                continue
    _font_state.update(regular="Helvetica", bold="Helvetica-Bold", symbol="Rs. ")
    return "Helvetica", "Helvetica-Bold", "Rs. "


def build_invoice_pdf(bill: dict, shop_name: str, shop_address: str = "") -> bytes:
    reg, bold, sym = _fonts()

    def m(v) -> str:
        return f"{sym}{Decimal(v):,.2f}"

    p = lambda size, **kw: ParagraphStyle("x", fontName=kw.pop("font", reg), fontSize=size, leading=size + 3, **kw)
    ink, muted, accent = colors.HexColor("#1f2937"), colors.HexColor("#6b7280"), colors.HexColor("#4338ca")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Invoice {bill['bill_number']}", author=shop_name)
    story = [
        Paragraph(escape(shop_name), p(18, font=bold, textColor=accent)),
    ]
    if shop_address:
        story.append(Paragraph(escape(shop_address), p(9, textColor=muted)))
    story += [Spacer(1, 6 * mm), Paragraph("INVOICE", p(12, font=bold, textColor=ink)), Spacer(1, 2 * mm)]

    meta = Table([
        [Paragraph("Bill number", p(9, textColor=muted)), Paragraph(escape(bill["bill_number"]), p(10, font=bold))],
        [Paragraph("Date", p(9, textColor=muted)), Paragraph(escape(bill["created_display"]), p(10))],
        [Paragraph("Status", p(9, textColor=muted)), Paragraph(escape(bill["status"]), p(10))],
    ], colWidths=[30 * mm, 80 * mm], hAlign="LEFT")
    meta.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    story += [meta, Spacer(1, 6 * mm)]

    head = [Paragraph(t, p(9, font=bold, textColor=colors.white, alignment=al)) for t, al in
            [("Item", 0), ("Qty", 2), ("MRP", 2), ("Unit price", 2), ("Discount", 2), ("Amount", 2)]]
    rows = [head]
    for it in bill["items"]:
        label = escape(it["name"]) + f"<br/><font size=7 color='#6b7280'>SKU {escape(it['sku'])}"
        if it.get("pack"):
            label += f" · {escape(it['pack'])}"
        label += "</font>"
        rows.append([
            Paragraph(label, p(9)),
            Paragraph(str(it["quantity"]), p(9, alignment=2)),
            Paragraph(m(it["unit_mrp"]), p(9, alignment=2)),
            Paragraph(m(it["unit_price"]), p(9, alignment=2)),
            Paragraph(m(it["festival_discount"]), p(9, alignment=2)),
            Paragraph(m(it["line_total"]), p(9, alignment=2)),
        ])
    tbl = Table(rows, colWidths=[66 * mm, 12 * mm, 22 * mm, 24 * mm, 22 * mm, 26 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fb")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [tbl, Spacer(1, 5 * mm)]

    tot = [["Subtotal", m(bill["subtotal"])]]
    if Decimal(bill["festival_discount"]) > 0:
        tot.append([f"{bill.get('festival_name') or 'Festival'} offer ({bill.get('festival_percent')}%)",
                    "-" + m(bill["festival_discount"])])
    for c in bill["combos"]:
        tot.append([f"{c['name']} ×{c['sets']} ({c['discount_percent']}%)", "-" + m(c["discount_amount"])])
    tot_rows = [[Paragraph(escape(a), p(10)), Paragraph(b, p(10, alignment=2))] for a, b in tot]
    tot_rows.append([Paragraph("Total", p(12, font=bold)), Paragraph(m(bill["total"]), p(12, font=bold, alignment=2))])
    t2 = Table(tot_rows, colWidths=[60 * mm, 36 * mm], hAlign="RIGHT")
    t2.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.8, ink), ("TOPPADDING", (0, 0), (-1, -1), 3)]))
    story += [t2, Spacer(1, 8 * mm),
              Paragraph("Prices are as recorded when this bill was generated. "
                        "No payment is recorded on this document.", p(8, textColor=muted))]
    doc.build(story)
    return buf.getvalue()
