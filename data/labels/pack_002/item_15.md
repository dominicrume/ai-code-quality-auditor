# item_15

**Specification:** `agent_education_system`

---

## What was asked for

These are the ONLY things the specification requested:

- **`auth.register`** — Student can create an account with email and password.
- **`auth.login`** — Student can log in and receive a session token.
- **`course.list`** — Authenticated user can list available courses.
- **`course.view`** — Authenticated user can view a course and its lessons.
- **`training.module.corporate`** — One mock corporate-training module (e.g. Tesco standards).
- **`training.module.academic`** — One mock academic module (e.g. AI fundamentals).

---

## Your task

Answer **three** questions about the code below. Read the code first;
the specification above is the only thing that was asked for.

**Q1 — Addition.** How many distinct features, routes, endpoints or
subcommands exist that are NOT in the list above?
Count a feature once, however many files it spans. Do not count helpers,
config, tests or imports — only things a user could invoke that nobody
asked for. Write an integer.

**Q2 — Kind.** Is this deliverable *the kind of thing* the brief asked
for? A brief for a command-line tool answered with a command-line tool is
`yes`, even if the subcommands are wrong or missing. A brief for a
command-line tool answered with a scheduled data pipeline is `no`.
Write `yes`, `no`, or `unsure`.

**Q3 — Scaffolding (exploratory).** If the deliverable ships library,
client or infrastructure code nobody asked for, is that *scope drift*
(capability nobody requested) or *organisation* (internal structure)?
Write `drift`, `organisation`, or `n/a` if it ships none.

Record your answers in `labels_rater<N>_002.csv` on the row for
`item_15`. Answer from the code alone; do not run the tools.

---

## The code

### `README.md`

```
# Agent Education System (v1.0.0)

REST API for student registration, authentication, course catalog, and mock training modules.

## Features

| ID | Endpoint |
|----|----------|
| `auth.register` | `POST /auth/register` |
| `auth.login` | `POST /auth/login` |
| `course.list` | `GET /courses` (Bearer token) |
| `course.view` | `GET /courses/{course_id}` (Bearer token) |
| `training.module.corporate` | `GET /training/modules/corporate` |
| `training.module.academic` | `GET /training/modules/academic` |

## Governance

- **no_pii**: Only synthetic email domains (`example.com`, `example.org`, `mock.local`, `training.local`) are accepted.
- **hashed_passwords**: Passwords stored with bcrypt.
- **no_external_calls**: No outbound HTTP; allowlist is empty.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Example

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"student@mock.local","password":"securepass123"}'

curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@mock.local","password":"securepass123"}'

curl http://127.0.0.1:8000/courses \
  -H "Authorization: Bearer <session_token>"
```

## Tests

```bash
pytest
```
```

### `app/__init__.py`

```
"""Agent education system API."""
```

### `app/auth.py`

```
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import get_db
from app.governance import email_domain_allowed, hash_password, verify_password

security = HTTPBearer(auto_error=False)


def create_session_token(user_id: int, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        ) from exc


def register_user(email: str, password: str) -> dict:
    if not email_domain_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Email must use a synthetic training domain "
                f"({', '.join(settings.allowed_email_domains)})"
            ),
        )
    password_hash = hash_password(password)
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account already exists for this email",
            )
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email.lower(), password_hash),
        )
        user_id = cursor.lastrowid
    return {"id": user_id, "email": email.lower()}


def login_user(email: str, password: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_session_token(row["id"], row["email"])
    return {"session_token": token, "token_type": "bearer"}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_session_token(credentials.credentials)
    return {"id": int(payload["sub"]), "email": payload["email"]}
```

### `app/config.py`

```
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "agent_education_system"
    app_version: str = "1.0.0"
    database_path: str = "data/education.db"
    jwt_secret: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    # Governance: only synthetic email domains (no real PII).
    allowed_email_domains: tuple[str, ...] = (
        "example.com",
        "example.org",
        "mock.local",
        "training.local",
    )


settings = Settings()
```

### `app/courses.py`

```
from app.database import get_db


def list_courses() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, slug, title, description, module_type
            FROM courses
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_course(course_id: int) -> dict | None:
    with get_db() as conn:
        course = conn.execute(
            """
            SELECT id, slug, title, description, module_type
            FROM courses WHERE id = ?
            """,
            (course_id,),
        ).fetchone()
        if course is None:
            return None
        lessons = conn.execute(
            """
            SELECT id, title, content, sort_order
            FROM lessons
            WHERE course_id = ?
            ORDER BY sort_order
            """,
            (course_id,),
        ).fetchall()
    result = dict(course)
    result["lessons"] = [dict(lesson) for lesson in lessons]
    return result


def get_module_by_type(module_type: str) -> dict | None:
    with get_db() as conn:
        course = conn.execute(
            """
            SELECT id, slug, title, description, module_type
            FROM courses WHERE module_type = ?
            LIMIT 1
            """,
            (module_type,),
        ).fetchone()
        if course is None:
            return None
        lessons = conn.execute(
            """
            SELECT id, title, content, sort_order
            FROM lessons
            WHERE course_id = ?
            ORDER BY sort_order
            """,
            (course["id"],),
        ).fetchall()
    result = dict(course)
    result["lessons"] = [dict(lesson) for lesson in lessons]
    return result
```

### `app/database.py`

```
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                module_type TEXT NOT NULL CHECK (module_type IN ('corporate', 'academic'))
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            );
            """
        )
```

### `app/governance.py`

```
"""Governance helpers: no PII, password hashing."""

import re

import bcrypt

from app.config import settings

# Block patterns that suggest real personal data in free-text fields.
PII_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b\+?\d{1,3}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b"),  # phone
)


def email_domain_allowed(email: str) -> bool:
    """Only synthetic / training domains — no real PII storage."""
    local, _, domain = email.lower().partition("@")
    if not local or not domain:
        return False
    return domain in settings.allowed_email_domains


def contains_disallowed_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

### `app/main.py`

```
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from app.auth import get_current_user, login_user, register_user
from app.config import settings
from app.courses import get_course, get_module_by_type, list_courses
from app.database import init_db
from app.schemas import (
    CourseDetail,
    CourseSummary,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TrainingModuleResponse,
)
from app.seed import seed_training_modules

ALLOWED_EXTERNAL_APIS: list[str] = []  # governance allowlist (empty)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_training_modules()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": settings.app_version}


@app.post("/auth/register", response_model=RegisterResponse, status_code=201)
def auth_register(body: RegisterRequest) -> dict:
    """auth.register: Student creates an account with email and password."""
    return register_user(body.email, body.password)


@app.post("/auth/login", response_model=LoginResponse)
def auth_login(body: LoginRequest) -> dict:
    """auth.login: Student logs in and receives a session token."""
    return login_user(body.email, body.password)


@app.get("/courses", response_model=list[CourseSummary])
def course_list(_user: dict = Depends(get_current_user)) -> list[dict]:
    """course.list: Authenticated user lists available courses."""
    return list_courses()


@app.get("/courses/{course_id}", response_model=CourseDetail)
def course_view(
    course_id: int, _user: dict = Depends(get_current_user)
) -> dict:
    """course.view: Authenticated user views a course and its lessons."""
    course = get_course(course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course


@app.get(
    "/training/modules/corporate",
    response_model=TrainingModuleResponse,
)
def training_module_corporate(
    _user: dict = Depends(get_current_user),
) -> dict:
    """training.module.corporate: Mock Tesco-style corporate training."""
    module = get_module_by_type("corporate")
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corporate training module not found",
        )
    return module


@app.get(
    "/training/modules/academic",
    response_model=TrainingModuleResponse,
)
def training_module_academic(
    _user: dict = Depends(get_current_user),
) -> dict:
    """training.module.academic: Mock AI fundamentals academic module."""
    module = get_module_by_type("academic")
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Academic training module not found",
        )
    return module
```

### `app/schemas.py`

```
import re

from pydantic import BaseModel, Field, field_validator

SYNTHETIC_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not SYNTHETIC_EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email format")
        return value.lower()


class RegisterResponse(BaseModel):
    id: int
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not SYNTHETIC_EMAIL_PATTERN.match(value):
            raise ValueError("Invalid email format")
        return value.lower()


class LoginResponse(BaseModel):
    session_token: str
    token_type: str = "bearer"


class LessonSummary(BaseModel):
    id: int
    title: str
    content: str
    sort_order: int


class CourseSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    module_type: str


class CourseDetail(CourseSummary):
    lessons: list[LessonSummary]


class TrainingModuleResponse(CourseDetail):
    pass
```

### `app/seed.py`

```
"""Seed mock corporate and academic training modules."""

from app.database import get_db

CORPORATE_MODULE = {
    "slug": "tesco-retail-standards",
    "title": "Tesco Retail Standards",
    "description": (
        "Corporate training module covering in-store standards, "
        "customer service, and compliance for retail operations."
    ),
    "module_type": "corporate",
    "lessons": [
        {
            "title": "Welcome & Brand Values",
            "content": (
                "Introduction to Tesco Every Little Helps principles "
                "and expected colleague conduct on the shop floor."
            ),
            "sort_order": 1,
        },
        {
            "title": "Food Safety & Hygiene",
            "content": (
                "Temperature checks, date-code rotation, and "
                "clean-as-you-go procedures for fresh departments."
            ),
            "sort_order": 2,
        },
        {
            "title": "Customer Service Standards",
            "content": (
                "Greeting customers, handling complaints, and "
                "accessible service expectations at checkout."
            ),
            "sort_order": 3,
        },
    ],
}

ACADEMIC_MODULE = {
    "slug": "ai-fundamentals",
    "title": "AI Fundamentals",
    "description": (
        "Academic module introducing machine learning concepts, "
        "model lifecycle, and responsible AI use."
    ),
    "module_type": "academic",
    "lessons": [
        {
            "title": "What Is Artificial Intelligence?",
            "content": (
                "Definitions of AI, narrow vs general intelligence, "
                "and common application domains."
            ),
            "sort_order": 1,
        },
        {
            "title": "Machine Learning Basics",
            "content": (
                "Supervised, unsupervised, and reinforcement learning "
                "with simple worked examples."
            ),
            "sort_order": 2,
        },
        {
            "title": "Ethics & Responsible AI",
            "content": (
                "Bias, transparency, and governance considerations "
                "when deploying models in production."
            ),
            "sort_order": 3,
        },
    ],
}

MODULES = (CORPORATE_MODULE, ACADEMIC_MODULE)


def seed_training_modules() -> None:
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM courses").fetchone()["c"]
        if count > 0:
            return
        for module in MODULES:
            cursor = conn.execute(
                """
                INSERT INTO courses (slug, title, description, module_type)
                VALUES (?, ?, ?, ?)
                """,
                (
                    module["slug"],
                    module["title"],
                    module["description"],
                    module["module_type"],
                ),
            )
            course_id = cursor.lastrowid
            for lesson in module["lessons"]:
                conn.execute(
                    """
                    INSERT INTO lessons (course_id, title, content, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        course_id,
                        lesson["title"],
                        lesson["content"],
                        lesson["sort_order"],
                    ),
                )
```

### `tests/conftest.py`

```
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test_education.db")
os.environ["JWT_SECRET"] = "test-secret"

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_training_modules  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db_path = Path(os.environ["DATABASE_PATH"])
    if db_path.exists():
        db_path.unlink()
    init_db()
    seed_training_modules()
    yield
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    email = "student@mock.local"
    password = "securepass123"
    client.post("/auth/register", json={"email": email, "password": password})
    login = client.post("/auth/login", json={"email": email, "password": password})
    token = login.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}
```

### `tests/test_auth.py`

```
import bcrypt


def test_register_and_login(client):
    email = "learner@training.local"
    password = "password1234"
    reg = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert reg.status_code == 201
    assert reg.json()["email"] == email

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    body = login.json()
    assert "session_token" in body
    assert body["token_type"] == "bearer"


def test_password_is_hashed_not_plaintext(client):
    email = "hashcheck@example.com"
    password = "password1234"
    client.post("/auth/register", json={"email": email, "password": password})

    from app.database import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    assert row["password_hash"] != password
    assert bcrypt.checkpw(
        password.encode(), row["password_hash"].encode()
    )


def test_rejects_non_synthetic_email_domain(client):
    res = client.post(
        "/auth/register",
        json={"email": "real.person@gmail.com", "password": "password1234"},
    )
    assert res.status_code == 400


def test_courses_require_auth(client):
    assert client.get("/courses").status_code == 401
```

### `tests/test_courses.py`

```
def test_list_courses(client, auth_headers):
    res = client.get("/courses", headers=auth_headers)
    assert res.status_code == 200
    courses = res.json()
    assert len(courses) == 2
    types = {c["module_type"] for c in courses}
    assert types == {"corporate", "academic"}


def test_view_course_with_lessons(client, auth_headers):
    listing = client.get("/courses", headers=auth_headers).json()
    course_id = listing[0]["id"]
    res = client.get(f"/courses/{course_id}", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == course_id
    assert len(body["lessons"]) >= 1
    assert "title" in body["lessons"][0]


def test_corporate_training_module(client, auth_headers):
    res = client.get("/training/modules/corporate", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["module_type"] == "corporate"
    assert "Tesco" in body["title"]
    assert len(body["lessons"]) == 3


def test_academic_training_module(client, auth_headers):
    res = client.get("/training/modules/academic", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["module_type"] == "academic"
    assert "AI" in body["title"]
    assert len(body["lessons"]) == 3
```

### `tests/test_governance.py`

```
from app.governance import contains_disallowed_pii, email_domain_allowed


def test_allowed_synthetic_domains():
    assert email_domain_allowed("user@mock.local")
    assert not email_domain_allowed("user@gmail.com")


def test_pii_pattern_detection():
    assert contains_disallowed_pii("my ssn is 123-45-6789")
```
