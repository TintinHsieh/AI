"""Small Campus Customs catalogue API for the Problem 3 storefront."""

from __future__ import annotations

import json
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from .agent import run_chat
    from .models import ChatHistoryMessage, ChatHistoryResponse, ChatRequest, ChatResponse, ProductMatch
except ImportError:  # Supports `uvicorn main:app` when launched from backend/.
    from agent import run_chat
    from models import ChatHistoryMessage, ChatHistoryResponse, ChatRequest, ChatResponse, ProductMatch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCTS_DIR = DATA_DIR / "products"
configured_auth_secret = os.getenv("AUTH_SECRET")
AUTH_SECRET = configured_auth_secret.encode() if configured_auth_secret else secrets.token_bytes(32)
SESSION_TTL_SECONDS = 60 * 60 * 24


class StockLevel(BaseModel):
    size: str
    quantity: int


class Product(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_file_path: str
    image_url: str
    price: float
    stock: list[StockLevel]
    total_stock: int


class User(BaseModel):
    id: int
    name: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    created_at: str


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: User


app = FastAPI(title="Campus Customs Catalogue API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def open_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Database not found at {DB_PATH}. Place the local data pack in HW4/data.",
        )
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(decoded, list):
        return [str(item) for item in decoded]
    return []


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hash a password with a random salt using the stdlib scrypt implementation."""

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"scrypt$16384$8$1${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    if encoded_hash.startswith("pbkdf2_sha256$"):
        try:
            algorithm, salt_value, digest_value = encoded_hash.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt_value.encode("utf-8"), 120_000
            )
            return hmac.compare_digest(actual.hex(), digest_value)
        except (TypeError, ValueError):
            return False
    try:
        algorithm, n_value, r_value, p_value, salt_value, digest_value = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False
        padding = "=" * (-len(salt_value) % 4)
        salt = base64.urlsafe_b64decode((salt_value + padding).encode("ascii"))
        padding = "=" * (-len(digest_value) % 4)
        expected = base64.urlsafe_b64decode((digest_value + padding).encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def public_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        created_at=row["created_at"],
    )


def encode_token_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def create_session_token(user: User) -> str:
    payload = encode_token_payload({
        "sub": user.id,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    })
    signature = hmac.new(AUTH_SECRET, payload.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload}.{encoded_signature}"


def current_user(authorization: str | None) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="A valid bearer token is required")
    try:
        payload_value, signature_value = authorization[7:].split(".", 1)
        supplied_signature = base64.urlsafe_b64decode(signature_value + "===")
        expected_signature = hmac.new(
            AUTH_SECRET, payload_value.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        payload_padding = "=" * (-len(payload_value) % 4)
        payload = json.loads(base64.urlsafe_b64decode((payload_value + payload_padding).encode("ascii")))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired token")
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None

    connection = open_db()
    try:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Account no longer exists")
        return public_user(row)
    finally:
        connection.close()


def product_matches_from_json(value: str | None) -> list[ProductMatch]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(decoded, list):
        return []
    matches: list[ProductMatch] = []
    for item in decoded[:8]:
        try:
            matches.append(ProductMatch.model_validate(item))
        except Exception:
            continue
    return matches


def persist_chat_turn(user_id: int, shopper_message: str, response: ChatResponse) -> None:
    """Atomically append a user/assistant turn for a logged-in shopper."""

    connection = open_db()
    try:
        connection.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, "user", shopper_message),
        )
        connection.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, ?, ?, ?)",
            (
                user_id,
                "assistant",
                response.reply,
                json.dumps([match.model_dump() for match in response.matches], ensure_ascii=False),
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def chat_history_for_user(user_id: int) -> ChatHistoryResponse:
    connection = open_db()
    try:
        rows = connection.execute(
            """
            SELECT id, role, content, products_json, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY id ASC
            LIMIT 200
            """,
            (user_id,),
        ).fetchall()
        return ChatHistoryResponse(
            messages=[
                ChatHistoryMessage(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    matches=product_matches_from_json(row["products_json"]),
                    created_at=row["created_at"],
                )
                for row in rows
                if row["role"] in {"user", "assistant"}
            ]
        )
    finally:
        connection.close()


def product_from_row(row: sqlite3.Row, inventory_rows: list[sqlite3.Row]) -> Product:
    stock = [StockLevel(size=item["size"], quantity=item["quantity"]) for item in inventory_rows]
    image_file_path = row["image_file_path"]
    return Product(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        colors=parse_json_list(row["colors"]),
        search_tags=parse_json_list(row["search_tags"]),
        image_file_path=image_file_path,
        image_url=f"/api/images/{quote(image_file_path, safe='/')}",
        price=float(row["price"]),
        stock=stock,
        total_stock=sum(item.quantity for item in stock),
    )


def fetch_products(search: str | None = None, garment_type: str | None = None) -> list[Product]:
    connection = open_db()
    try:
        query = "SELECT * FROM catalogue"
        clauses: list[str] = []
        params: list[str] = []
        if search:
            term = f"%{search.lower()}%"
            clauses.append(
                "(lower(name) LIKE ? OR lower(garment_type) LIKE ? OR lower(description) LIKE ? "
                "OR lower(colors) LIKE ? OR lower(search_tags) LIKE ?)"
            )
            params.extend([term] * 5)
        if garment_type:
            clauses.append("garment_type = ?")
            params.append(garment_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY name COLLATE NOCASE"

        catalogue_rows = connection.execute(query, params).fetchall()
        inventory_rows = connection.execute(
            "SELECT product_id, size, quantity FROM inventory ORDER BY product_id, size"
        ).fetchall()
        inventory_by_product: dict[str, list[sqlite3.Row]] = {}
        for inventory_row in inventory_rows:
            inventory_by_product.setdefault(inventory_row["product_id"], []).append(inventory_row)
        return [
            product_from_row(row, inventory_by_product.get(row["product_id"], []))
            for row in catalogue_rows
        ]
    finally:
        connection.close()


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"ok": True, "database_available": DB_PATH.exists()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    shopper = current_user(authorization) if authorization else None
    try:
        response = await run_chat(
            request.message,
            page_context=request.page_context,
            user_id=shopper.id if shopper else None,
            user_name=shopper.name if shopper else None,
            user_email=shopper.email if shopper else None,
        )
        if shopper:
            persist_chat_turn(shopper.id, request.message.strip(), response)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="The chat service is not configured yet.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The chat service could not complete that request.") from exc


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
def chat_history(authorization: str | None = Header(default=None)) -> ChatHistoryResponse:
    shopper = current_user(authorization)
    return chat_history_for_user(shopper.id)


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest) -> AuthResponse:
    first_name = request.first_name.strip()
    last_name = request.last_name.strip()
    email = normalize_email(request.email)
    if not first_name or not last_name or not email:
        raise HTTPException(status_code=400, detail="First name, last name, and email are required")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    connection = open_db()
    try:
        existing = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            raise HTTPException(status_code=409, detail="An account with that email already exists")
        cursor = connection.execute(
            "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (f"{first_name} {last_name}", email, hash_password(request.password), first_name, last_name),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Account could not be loaded after creation")
        user = public_user(row)
        return AuthResponse(token=create_session_token(user), user=user)
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists") from exc
    finally:
        connection.close()


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest) -> AuthResponse:
    email = normalize_email(request.email)
    connection = open_db()
    try:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None or not verify_password(request.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user = public_user(row)
        return AuthResponse(token=create_session_token(user), user=user)
    finally:
        connection.close()


@app.get("/api/auth/me", response_model=User)
def me(authorization: str | None = Header(default=None)) -> User:
    return current_user(authorization)


@app.get("/api/products", response_model=list[Product])
def products(search: str | None = None, garment_type: str | None = None) -> list[Product]:
    return fetch_products(search=search, garment_type=garment_type)


@app.get("/api/products/{product_id}", response_model=Product)
def product(product_id: str) -> Product:
    connection = open_db()
    try:
        row = connection.execute(
            "SELECT * FROM catalogue WHERE product_id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        stock = connection.execute(
            "SELECT product_id, size, quantity FROM inventory WHERE product_id = ? ORDER BY size",
            (product_id,),
        ).fetchall()
        return product_from_row(row, stock)
    finally:
        connection.close()


@app.get("/api/images/{image_path:path}", name="product_image")
def product_image(image_path: str) -> FileResponse:
    requested = (DATA_DIR / image_path).resolve()
    products_root = PRODUCTS_DIR.resolve()
    try:
        requested.relative_to(products_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(requested)
