"""Loads festival and combo offers from backend/app/data/offers.json."""
import json
import logging
from decimal import Decimal

from ..config import settings
from .billing import ComboOffer, FestivalOffer, parse_date

log = logging.getLogger("smart_retail.offers")


def load_offers(path=None):
    path = path or settings.offers_file
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.warning("Offers file %s not found; no offers will apply.", path)
        return [], []
    except (OSError, ValueError) as exc:
        log.error("Could not read offers file %s: %s", path, exc)
        return [], []

    festivals, combos = [], []
    for f in raw.get("festivals", []):
        try:
            festivals.append(FestivalOffer(
                f["name"], parse_date(f["start_date"]), parse_date(f["end_date"]),
                Decimal(str(f["discount_percent"])),
            ))
        except (KeyError, ValueError) as exc:
            log.error("Skipping invalid festival offer %r: %s", f, exc)
    for c in raw.get("combos", []):
        try:
            combos.append(ComboOffer(
                c["name"], tuple(s.strip().upper() for s in c["skus"]),
                Decimal(str(c["discount_percent"])),
            ))
        except (KeyError, ValueError, AttributeError) as exc:
            log.error("Skipping invalid combo %r: %s", c, exc)
    return festivals, combos
