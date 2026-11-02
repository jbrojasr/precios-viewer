import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "prices.db"
MAX_UPLOAD = 12 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                description TEXT NOT NULL,
                stock REAL NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0,
                search_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_products_code ON products(code);
            CREATE INDEX IF NOT EXISTS idx_products_search ON products(search_text);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(products)")}
        if "price" in columns and "cost" not in columns:
            conn.execute("ALTER TABLE products RENAME COLUMN price TO cost")


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value.lower()).strip()


def clean_header(value):
    return re.sub(r"[^a-z0-9]", "", normalize(value))


def numeric(value, field):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace("$", "").replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"El valor de {field} no es numérico: {value}") from exc


HEADER_ALIASES = {
    "code": {"codigo", "cod", "sku", "referencia", "ref"},
    "description": {"descripcion", "producto", "nombre", "articulo"},
    "stock": {"existencia", "existencias", "stock", "cantidad", "disponible"},
    "cost": {"costototal", "costo", "preciototal", "precio", "precioventa", "pvp", "total"},
}


def parse_workbook(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        headers = next(rows)
    except StopIteration as exc:
        raise ValueError("El archivo está vacío") from exc

    normalized_headers = [clean_header(item) for item in headers]
    columns = {}
    for key, aliases in HEADER_ALIASES.items():
        for index, header in enumerate(normalized_headers):
            if header in aliases:
                columns[key] = index
                break
    missing = [key for key in HEADER_ALIASES if key not in columns]
    if missing:
        labels = {"code": "Código", "description": "Descripción", "stock": "Existencia", "cost": "Costo"}
        raise ValueError("Faltan columnas requeridas: " + ", ".join(labels[key] for key in missing))

    products = []
    errors = []
    for row_number, row in enumerate(rows, start=2):
        code = str(row[columns["code"]] or "").strip()
        description = str(row[columns["description"]] or "").strip()
        if not code and not description:
            continue
        if not code or not description:
            errors.append(f"Fila {row_number}: falta código o descripción")
            continue
        try:
            stock = numeric(row[columns["stock"]], "existencia")
            cost = numeric(row[columns["cost"]], "costo")
        except ValueError as exc:
            errors.append(f"Fila {row_number}: {exc}")
            continue
        products.append((code, description, stock, cost, normalize(f"{code} {description}")))

    if not products:
        detail = errors[0] if errors else "No se encontraron productos"
        raise ValueError(detail)
    return products, errors, sheet.title


def import_workbook(path, original_name):
    products, errors, sheet_name = parse_workbook(path)
    now = datetime.now(timezone.utc).isoformat()
    deduplicated = {item[0]: item for item in products}
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM products")
        conn.executemany(
            "INSERT INTO products(code, description, stock, cost, search_text, updated_at) VALUES(?,?,?,?,?,?)",
            [(*item, now) for item in deduplicated.values()],
        )
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('last_import',?)", (now,))
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('source_file',?)", (original_name,))
    return {"count": len(deduplicated), "errors": errors[:10], "sheet": sheet_name, "updated_at": now}


def get_setting(key):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def verify_pin(pin):
    salt = get_setting("pin_salt")
    expected = get_setting("pin_hash")
    if not salt or not expected:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 180000).hex()
    return hmac.compare_digest(actual, expected)


def set_pin(pin):
    if not re.fullmatch(r"\d{4,10}", pin):
        raise ValueError("La clave debe tener entre 4 y 10 números")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, 180000).hex()
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('pin_salt',?)", (salt.hex(),))
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('pin_hash',?)", (digest,))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/stats")
def stats():
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) count, COALESCE(SUM(stock),0) units, COALESCE(SUM(CASE WHEN stock > 0 THEN 1 ELSE 0 END),0) available FROM products"
        ).fetchone()
    return jsonify(
        count=row["count"],
        units=row["units"],
        available=row["available"],
        updated_at=get_setting("last_import"),
        source_file=get_setting("source_file"),
        pin_configured=bool(get_setting("pin_hash")),
    )


@app.get("/api/products")
def products():
    raw_query = request.args.get("q", "")
    search_in_description = raw_query.startswith("*")
    if search_in_description:
        raw_query = raw_query[1:].strip()

    query = normalize(raw_query)
    try:
        limit = min(max(int(request.args.get("limit", 80)), 1), 300)
    except ValueError:
        limit = 80
    terms = [term for term in query.split(" ") if term][:8]

    if search_in_description:
        where = " AND ".join("description LIKE ?" for _ in terms) or "1=1"
    else:
        where = " AND ".join("search_text LIKE ?" for _ in terms) or "1=1"

    params = [f"%{term}%" for term in terms]
    with db() as conn:
        rows = conn.execute(
            f"SELECT code, description, stock, cost FROM products WHERE {where} ORDER BY CASE WHEN stock > 0 THEN 0 ELSE 1 END, description LIMIT ?",
            (*params, limit),
        ).fetchall()
        count = conn.execute(f"SELECT COUNT(*) count FROM products WHERE {where}", params).fetchone()["count"]
    return jsonify(count=count, items=[dict(row) for row in rows])


@app.post("/api/setup-pin")
def setup_pin():
    if get_setting("pin_hash"):
        return jsonify(error="La clave ya está configurada"), 409
    payload = request.get_json(silent=True) or {}
    try:
        set_pin(str(payload.get("pin", "")))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True)


@app.post("/api/import")
def upload():
    if not get_setting("pin_hash"):
        return jsonify(error="Primero configura una clave de actualización"), 403
    if not verify_pin(request.form.get("pin", "")):
        return jsonify(error="Clave incorrecta"), 403
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify(error="Selecciona un archivo Excel"), 400
    if not uploaded.filename.lower().endswith(".xlsx"):
        return jsonify(error="Solo se permiten archivos .xlsx"), 400
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(uploaded.filename).name)
    target = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    uploaded.save(target)
    try:
        result = import_workbook(target, uploaded.filename)
    except Exception as exc:
        target.unlink(missing_ok=True)
        return jsonify(error=str(exc)), 400
    for old_file in sorted(UPLOAD_DIR.glob("*.xlsx"), reverse=True)[3:]:
        old_file.unlink(missing_ok=True)
    return jsonify(ok=True, **result)


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="El archivo supera el límite de 12 MB"), 413


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), threaded=True)
