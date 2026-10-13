"""Command line management.

    python -m app.manage init-db
    python -m app.manage create-user --username shop --role admin      (prompts for password)
    python -m app.manage seed-catalog                                  (adds the 8 original classes)
"""
import argparse
import getpass
import sys
from decimal import Decimal

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import Product, User
from .security import hash_password

# Prices come from `base_prices` in Detect_Classify_Bill.ipynb. The notebook has no MRP,
# pack size or brand data, so MRP is set equal to that price and pack size is left blank:
# edit these in the Products screen.
SEED = [
    ("AMUL-ICE-CREAM", "Amul Ice Cream", "Amul", "Amul_Ice_Cream", "30"),
    ("CAKE", "Cake", "", "Cake", "30"),
    ("CERAVE", "CeraVe", "CeraVe", "CeraVe", "900"),
    ("HNS-SHAMPOO", "Head & Shoulders Shampoo", "Head & Shoulders", "HnS_Shampoo", "250"),
    ("NESTLE-MILK-POWDER", "Nestle Milk Powder", "Nestle", "Nestle_Milk_Powder", "10"),
    ("PLUM", "Plum", "Plum", "Plum", "350"),
    ("THUMS-UP", "Thums Up", "Thums Up", "Thums_Up", "20"),
    ("WILD-STONE", "Wild Stone", "Wild Stone", "Wild_Stone", "70"),
]


def create_user(username, role, password=None, full_name=""):
    init_db()
    username = username.strip().lower()
    password = password or getpass.getpass("Password (min 10 chars): ")
    if len(password) < 10:
        sys.exit("Password must be at least 10 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == username)):
            sys.exit(f"User '{username}' already exists.")
        db.add(User(username=username, full_name=full_name or username, role=role,
                    password_hash=hash_password(password)))
        db.commit()
    print(f"Created {role} '{username}'.")


def seed_catalog():
    init_db()
    added = 0
    with SessionLocal() as db:
        for sku, name, brand, ai_class, price in SEED:
            if db.scalar(select(Product).where(Product.sku == sku)):
                continue
            db.add(Product(sku=sku, name=name, brand=brand, ai_class=ai_class,
                           mrp=Decimal(price), selling_price=Decimal(price)))
            added += 1
        db.commit()
    print(f"Seeded {added} product(s); {len(SEED) - added} already existed.")


def main():
    ap = argparse.ArgumentParser(prog="app.manage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    cu = sub.add_parser("create-user")
    cu.add_argument("--username", required=True)
    cu.add_argument("--role", choices=["admin", "cashier"], default="cashier")
    cu.add_argument("--full-name", default="")
    sub.add_parser("seed-catalog")
    a = ap.parse_args()
    if a.cmd == "init-db":
        init_db()
        print("Database initialised.")
    elif a.cmd == "create-user":
        create_user(a.username, a.role, full_name=a.full_name)
    elif a.cmd == "seed-catalog":
        seed_catalog()


if __name__ == "__main__":
    main()
