# Smart Retail Checkout

A shop billing application built around the AI pipeline from
**AI-Powered Object Detection and Smart Billing System** (original project by Rohith Reddy, MIT licence — see `LICENSE`, `README_ORIGINAL.md`).

Scan products with a camera or a photo, review what the AI found, confirm the exact SKU, generate a bill, download an invoice PDF — and manage products and prices from an admin screen, without editing Python.

> ## Verification status — please read
> This code was written in a sandbox **without internet access**, so FastAPI, SQLAlchemy, TensorFlow and Ultralytics could not be installed there. Consequently:
>
> | Part | Status |
> |---|---|
> | Billing engine, offers, security (hashing/JWT), image validation, AI post-processing, PDF invoice | **Unit-tested and passing** (24 tests, `backend/tests/test_core.py`) |
> | Front end (all screens, camera flow, forms, cart, admin) | **Tested in real Chromium (43 checks passing)** against a *stand-in* HTTP server that reused the real billing/image/PDF modules. The stand-in is not FastAPI. |
> | FastAPI routes, SQLAlchemy models, auth dependencies (`backend/app/routers`, `models.py`, `main.py`) | **Written and syntax-checked only. Never executed.** `backend/tests/test_api.py` was written for them but **has not been run**. Expect to fix small issues on first run. |
> | YOLO + MobileNetV2 inference (`ai_service.py`) | **Never run.** The trained weights are not in the repository. No accuracy claim is made. |
> | Windows scripts, Flutter | Scripts untested. **Flutter was not used** (see Limitations). |
>
> Run `scripts\test.ps1` first; that is the real verification of the backend.

## Architecture

```
Browser (frontend/: HTML + CSS + vanilla JS, served by FastAPI)
   │  REST + JWT
FastAPI (backend/app)
   ├─ routers: auth · products (admin CRUD, images) · scan · bills (+PDF) · dashboard
   ├─ services/billing.py       pure Decimal pricing engine (server is the only authority on totals)
   ├─ services/offers.py        festival + combo offers from app/data/offers.json (ported from the notebook)
   ├─ services/ai_service.py    YOLOv8m → box filtering → MobileNetV2 (models loaded once at start-up)
   ├─ services/pdf_invoice.py   ReportLab invoices
   └─ SQLAlchemy + SQLite       users, products, product_images, bills, bill_items (price snapshot), bill_combos
```

## Prerequisites (Windows 11)
* Python **3.11 or 3.12** (3.12 used for development). If you install the AI extras, use the Python version your TensorFlow wheel supports.
* The AI model files (below) — optional; without them the app runs in **manual billing mode**.

## Setup
```powershell
scripts\setup.ps1                  # venv + app dependencies + backend\.env (random secret) + empty database
scripts\setup.ps1 -WithAI          # also TensorFlow + Ultralytics (several GB)
scripts\create_admin.ps1 -Username shopowner -Seed     # creates/resets an admin with hidden password prompts; -Seed adds products
cd backend; ..\.venv\Scripts\python.exe -m app.manage provision-admin --username ravi  # prompts to create/reset an admin
scripts\run.ps1                    # http://localhost:8000   (API docs: http://localhost:8000/docs)
scripts\test.ps1                   # pytest
```
Open **http://localhost:8000** (not a LAN IP): browsers only allow camera access on `localhost` or HTTPS. On a phone over plain HTTP the camera preview is blocked, but **Upload / take photo** still works.

Create more users: `cd backend; ..\.venv\Scripts\python -m app.manage create-user --username till1 --role cashier`.

## Configuration
Copy `backend/.env.example` to `backend/.env` (done by `setup.ps1`). Secrets live only in `.env`; `SMART_CORS_ORIGINS` is an explicit list (never `*`). **Local-demo vs production:** this setup is for a single shop on one PC. For anything public, add HTTPS, a real `SMART_SECRET_KEY`, login rate limiting (not implemented), backups, and review CORS.

## Registration, administrator provisioning, and Render

The public **Create account** page and `POST /api/auth/register` create cashier accounts only. The request schema rejects extra fields such as `role`, and usernames are normalized and checked for duplicates. Administrator access must be provisioned through the management CLI. Passwords are prompted without echo, confirmed, and stored only as scrypt hashes.

The API and frontend are served by the same FastAPI service. The frontend calls root-relative `/api/...` URLs, so it uses the deployed host automatically; do not put a localhost URL in frontend code. CORS is needed only if the frontend is hosted on a different origin, in which case set `SMART_CORS_ORIGINS` to that exact HTTPS origin.

There is no Render manifest or hosted-service URL in this repository, so the actual Render service settings and production database cannot be inspected from this checkout. The application uses `SMART_DATABASE_URL` first, then Render's standard `DATABASE_URL`, and otherwise defaults to SQLite at `backend/data/smart_retail.db`. Do not run the provisioning command on a developer machine and assume it changed the Render database.

### Render service setup and deployment

1. In the Render dashboard, inspect the existing service's **Root Directory**, **Build Command**, **Start Command**, **Environment**, and attached disk/database before changing anything. Preserve the existing database. There are no Alembic migrations; startup calls SQLAlchemy `create_all`, and this change adds no schema columns.
2. Ensure the build installs `backend/requirements.txt` (from the repository root, `pip install -r backend/requirements.txt`). The backend supports SQLite and PostgreSQL; PostgreSQL URLs are connected through the psycopg driver installed from that requirements file.
3. If the service root is the repository root, a compatible start command is `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`. If Render's root directory is already `backend`, use `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Set a stable, random `SMART_SECRET_KEY` of at least 32 characters in Render's protected environment settings. Set `SMART_DATABASE_URL` to the production database URL if using PostgreSQL, or confirm Render's `DATABASE_URL` is present (it is used if `SMART_DATABASE_URL` is unset). Keep the URL in Render only; never paste it into source control or a local terminal. If using SQLite, attach a persistent disk and point `SMART_DATABASE_URL` at the database file on that disk; Render's default ephemeral filesystem is not durable across restarts/redeploys.
5. Deploy and wait for the service to become healthy. Confirm `https://<your-service-host>/api/health` returns HTTP 200 with `status` set to `ok` and the root page loads before provisioning.
6. Open the **Shell for that same running Render web service** (not a local terminal and not a separate service with different environment variables), change to the backend directory if needed, and run the existing account setup command:

   ```sh
   cd backend
   python -m app.manage provision-admin --username ravi --full-name Ravi
   ```

   Enter and confirm the temporary viva password at the hidden prompts. Do not add it as a command-line argument or print it; the command refuses to prompt unless it has a terminal that can keep the password hidden. The command safely creates the admin if absent, or resets that matching account's password, role, and active flag. It never deletes other users, products, bills, or records. It reports only whether the account was created or updated.
7. Visit `https://<your-service-host>/`, sign in using the provisioned credentials, and confirm the dashboard loads. Verify existing products and a test checkout before the viva. If provisioning or login fails, inspect Render service logs and verify that the Shell belongs to the web service, its selected `SMART_DATABASE_URL`/`DATABASE_URL` points to the intended production DB, and the database permits connections from the service. For `No module named psycopg`, confirm the requirements build completed and redeploy. For cross-origin frontend hosting, verify the exact frontend origin is in `SMART_CORS_ORIGINS`.

The production login is not verified by this repository change: it requires access to the actual Render service, its configured database, and its public URL. After the viva, change the temporary password using the same Shell command and choose a longer, unique password.

## AI model setup
The GitHub repository does **not** contain these (they are git-ignored). Place them in the project root, or point `SMART_KERAS_MODEL` / `SMART_YOLO_MODEL` at them:
* `full_model.keras` — produced by `Model_Training.ipynb` (train it in Colab with the dataset; the notebook trained for 5 epochs). Size depends on the model; MobileNetV2 + head is typically tens of MB.
* `yolov8m.pt` — pretrained YOLOv8m weights (~50 MB), downloadable from Ultralytics. Not downloaded automatically.

`GET /api/scan/status` (and the scan page) reports whether models loaded and why not. If unavailable, `/api/scan` returns `ai_available: false` with **no detections**; nothing is ever fabricated, and manual billing is unaffected.

### Findings from the original notebooks (corrected in `ai_service.py`)
1. **Preprocessing mismatch.** `Model_Training.ipynb` trains with MobileNetV2 `preprocess_input` (inputs scaled to −1…1) but `Detect_Classify_Bill.ipynb` divided crops by 255. The service uses `preprocess_input`.
2. **BGR vs RGB.** The notebook fed OpenCV BGR crops to a model trained on RGB. The service converts to RGB.
3. **Filtered boxes unused.** The notebook computed `fil_detections` and then classified the unfiltered `detections`. The service classifies the filtered list. `remove_nested_boxes` (IoU>0.7) is kept as-is; a containment filter (`remove_contained_boxes`) was **added** because IoU cannot catch a small box fully inside a large one.
4. **Generic detector.** `yolov8m.pt` is COCO-pretrained, not trained on these products; whether it localises ice-cream tubs, cakes or CeraVe tubs is **untested**. If recall is poor, fine-tune YOLO on product boxes.
5. **Festival offers** in the notebook are 2025 dates (all expired) and overlapping festivals compounded. Now only the single best active offer applies; dates are in `backend/app/data/offers.json`.
6. The README’s “92.45%” accuracy is the original author’s claim; it was not reproduced here.

### SKUs vs classes
The classifier outputs 8 **classes**, not SKUs. Each product has an optional `ai_class`. If exactly one active SKU maps to a class *and* confidence ≥ 0.8, it is pre-selected; otherwise the cashier must pick the SKU. Nothing is billed until the cashier confirms. **Adding a product does not teach the model to recognise it**: a brand-new product needs images added to `Dataset/<class>/`, re-running `Data_Augmentation.ipynb` + `Model_Training.ipynb` (with the new class in `SMART_CLASS_NAMES`, in alphabetical order, matching `flow_from_directory`). Reference images uploaded in the admin screen are stored for this future enrolment but are **not used** by the current model.

## Pricing rules
`unit price = selling price` from the catalog · one best active festival offer (per-unit rounding as in the notebook) · combo discounts on complete sets, applied on the festival price, a unit can join only one combo · Decimal, round-half-up · bill items store a snapshot (name, SKU, MRP, price) so later price edits don’t change old invoices · client-sent prices are ignored · repeating a bill submission with the same idempotency key returns the same bill. **Tax is not implemented** (prices are treated as final) and **payments are not recorded** — bills show “Payment not recorded”.
Discount is derived from MRP vs selling price; MRP ≥ selling price is enforced (also by a DB constraint). The seed catalog uses the notebook’s prices with MRP = price and no pack sizes, because the notebook has no such data — edit them in **Products**.

## Files
**Original (untouched):** the three notebooks, `Dataset/`, `Sample_Images/`, `LICENSE`, `README_ORIGINAL.md`.
**Added:** `backend/` (app, tests, requirements, `.env.example`), `frontend/`, `scripts/`, this README.
**Modified:** `.gitignore` (entries appended), `README.md` (original preserved as `README_ORIGINAL.md`).

## Known limitations
* No Flutter app: the repo had no frontend and Flutter couldn't be installed/verified, so a dependency-free responsive web UI is used (works in desktop and mobile browsers).
* No database migrations (Alembic); schema is created with `create_all`. Back up `backend/data/` before schema changes.
* Dataset note: `Dataset/Cake/final_project_images/` is a nested duplicate of the dataset; the augmentation notebook ignores it, but it is clutter.
* GPU: native-Windows TensorFlow ≥ 2.11 is CPU-only; YOLO (PyTorch) can use CUDA. No timings were measured.
* No login rate limiting, no password reset UI, single shop.
