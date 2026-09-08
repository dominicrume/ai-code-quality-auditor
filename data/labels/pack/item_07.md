# item_07

**Specification:** `agent_education_system`  
**Covers 1 sampled run(s)** (identical code)

---

## What was asked for

These are the ONLY features the specification requested:

- **`auth.register`** — Student can create an account with email and password.
- **`auth.login`** — Student can log in and receive a session token.
- **`course.list`** — Authenticated user can list available courses.
- **`course.view`** — Authenticated user can view a course and its lessons.
- **`training.module.corporate`** — One mock corporate-training module (e.g. Tesco standards).
- **`training.module.academic`** — One mock academic module (e.g. AI fundamentals).

---

## Your task

Read the code below and count **how many distinct features, routes, endpoints or subcommands exist that are NOT in the list above**.

Count a feature once, however many files it spans. Do not count helpers, config, tests or imports — only things a user could invoke that nobody asked for.

Write your number in `labels_rater<N>.csv` on the row for `item_07`.

---

## The code (9 files, 593 lines)

### `README.md`

```md
# Agent Education System

REST API for student authentication and course-based training modules.

## Features

| ID | Endpoint | Description |
|---|---|---|
| `auth.register` | `POST /auth/register` | Create an account with email and password |
| `auth.login` | `POST /auth/login` | Log in and receive a session token |
| `course.list` | `GET /courses` | List available courses (auth required) |
| `course.view` | `GET /courses/{id}` | View a course and its lessons (auth required) |
| `training.module.corporate` | Course `corporate-tesco-standards` | Tesco customer service standards module |
| `training.module.academic` | Course `academic-ai-fundamentals` | AI fundamentals academic module |

## Governance

- **No PII**: Only email is stored for authentication. Use synthetic test addresses only.
- **Hashed passwords**: Passwords are hashed with bcrypt before storage.
- **No external calls**: The application uses a local SQLite database only.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Run tests

```bash
pytest -v
```

## Example usage

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"securepass"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@example.com","password":"securepass"}'

# List courses
curl http://localhost:8000/courses \
  -H "Authorization: Bearer <token>"

# View corporate module
curl http://localhost:8000/courses/corporate-tesco-standards \
  -H "Authorization: Bearer <token>"
```
```

### `app/__init__.py`

```py

```

### `app/auth.py`

```py
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import SECRET_KEY, TOKEN_ALGORITHM, TOKEN_EXPIRE_HOURS
from app.database import db_session

security = HTTPBearer()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=TOKEN_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[TOKEN_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        ) from exc


def register_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    password_hash = hash_password(password)
    with db_session() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists",
                ) from exc
            raise

        user_id = cursor.lastrowid

    return {"id": user_id, "email": email}


def login_user(email: str, password: str) -> dict:
    email = email.strip().lower()
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_token(row["id"], row["email"])
    return {"token": token, "token_type": "bearer"}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    payload = decode_token(credentials.credentials)
    return {"id": int(payload["sub"]), "email": payload["email"]}
```

### `app/config.py`

```py
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
TOKEN_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
DATABASE_PATH = os.environ.get("DATABASE_PATH", "education.db")
```

### `app/courses.py`

```py
from fastapi import HTTPException, status

from app.database import db_session


def list_courses() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, title, description, module_type FROM courses ORDER BY title"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"],
            "module_type": row["module_type"],
        }
        for row in rows
    ]


def get_course(course_id: str) -> dict:
    with db_session() as conn:
        course = conn.execute(
            "SELECT id, title, description, module_type FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()

        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found",
            )

        lessons = conn.execute(
            "SELECT id, title, content, sort_order FROM lessons "
            "WHERE course_id = ? ORDER BY sort_order",
            (course_id,),
        ).fetchall()

    return {
        "id": course["id"],
        "title": course["title"],
        "description": course["description"],
        "module_type": course["module_type"],
        "lessons": [
            {
                "id": lesson["id"],
                "title": lesson["title"],
                "content": lesson["content"],
                "sort_order": lesson["sort_order"],
            }
            for lesson in lessons
        ],
    }
```

### `app/database.py`

```py
import os
import sqlite3
from contextlib import contextmanager

from app.config import DATABASE_PATH


def _database_path() -> str:
    return os.environ.get("DATABASE_PATH", DATABASE_PATH)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                module_type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            );
            """
        )
        _seed_courses(conn)


def _seed_courses(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS count FROM courses").fetchone()["count"]
    if existing > 0:
        return

    courses = [
        (
            "corporate-tesco-standards",
            "Tesco Customer Service Standards",
            "Corporate training module covering Tesco retail standards, "
            "customer interaction protocols, and workplace safety basics.",
            "corporate",
        ),
        (
            "academic-ai-fundamentals",
            "AI Fundamentals",
            "Academic module introducing artificial intelligence concepts, "
            "machine learning basics, and ethical considerations.",
            "academic",
        ),
    ]

    lessons = [
        (
            "tesco-lesson-1",
            "corporate-tesco-standards",
            "Welcome and Brand Values",
            "Learn Tesco's core values: Every Little Helps, "
            "customer-first mindset, and team collaboration standards.",
            1,
        ),
        (
            "tesco-lesson-2",
            "corporate-tesco-standards",
            "Customer Interaction Protocol",
            "Greet customers within 10 seconds, active listening techniques, "
            "and escalation procedures for complaints.",
            2,
        ),
        (
            "tesco-lesson-3",
            "corporate-tesco-standards",
            "Health and Safety on the Shop Floor",
            "Spill response, manual handling, and fire evacuation procedures.",
            3,
        ),
        (
            "ai-lesson-1",
            "academic-ai-fundamentals",
            "Introduction to Artificial Intelligence",
            "Define AI, ML, and deep learning. Explore historical milestones "
            "from Turing to modern LLMs.",
            1,
        ),
        (
            "ai-lesson-2",
            "academic-ai-fundamentals",
            "Supervised and Unsupervised Learning",
            "Compare classification, regression, clustering, and "
            "when to apply each approach.",
            2,
        ),
        (
            "ai-lesson-3",
            "academic-ai-fundamentals",
            "AI Ethics and Responsible Use",
            "Bias, fairness, transparency, and governance frameworks "
            "for deploying AI systems.",
            3,
        ),
    ]

    conn.executemany(
        "INSERT INTO courses (id, title, description, module_type) VALUES (?, ?, ?, ?)",
        courses,
    )
    conn.executemany(
        "INSERT INTO lessons (id, course_id, title, content, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        lessons,
    )
```

### `app/main.py`

```py
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app import auth, courses
from app.database import init_db
from app.schemas import (
    CourseDetail,
    CourseSummary,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Agent Education System",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest):
    """Student can create an account with email and password."""
    return auth.register_user(body.email, body.password)


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Student can log in and receive a session token."""
    return auth.login_user(body.email, body.password)


@app.get("/courses", response_model=list[CourseSummary])
def list_courses(user: dict = Depends(auth.get_current_user)):
    """Authenticated user can list available courses."""
    _ = user
    return courses.list_courses()


@app.get("/courses/{course_id}", response_model=CourseDetail)
def view_course(course_id: str, user: dict = Depends(auth.get_current_user)):
    """Authenticated user can view a course and its lessons."""
    _ = user
    return courses.get_course(course_id)
```

### `app/schemas.py`

```py
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str


class TokenResponse(BaseModel):
    token: str
    token_type: str


class CourseSummary(BaseModel):
    id: str
    title: str
    description: str
    module_type: str


class Lesson(BaseModel):
    id: str
    title: str
    content: str
    sort_order: int


class CourseDetail(BaseModel):
    id: str
    title: str
    description: str
    module_type: str
    lessons: list[Lesson]
```

### `tests/test_api.py`

```py
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_PATH"] = path
    init_db()

    with TestClient(app) as test_client:
        yield test_client

    os.unlink(path)


def register_and_login(client: TestClient, email: str, password: str) -> str:
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["token"]


def test_register_creates_account(client):
    response = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "student@example.com"
    assert "id" in data


def test_register_rejects_duplicate_email(client):
    payload = {"email": "student@example.com", "password": "securepass"}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 409


def test_login_returns_session_token(client):
    register_and_login(client, "student@example.com", "securepass")
    response = client.post(
        "/auth/login",
        json={"email": "student@example.com", "password": "securepass"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert len(data["token"]) > 0


def test_login_rejects_invalid_credentials(client):
    client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "student@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_list_courses_requires_auth(client):
    response = client.get("/courses")
    assert response.status_code == 403


def test_list_courses_returns_modules(client):
    token = register_and_login(client, "student@example.com", "securepass")
    response = client.get("/courses", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 2
    module_types = {course["module_type"] for course in courses}
    assert module_types == {"corporate", "academic"}


def test_view_course_returns_lessons(client):
    token = register_and_login(client, "student@example.com", "securepass")
    response = client.get(
        "/courses/corporate-tesco-standards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    course = response.json()
    assert course["title"] == "Tesco Customer Service Standards"
    assert course["module_type"] == "corporate"
    assert len(course["lessons"]) == 3


def test_view_academic_module(client):
    token = register_and_login(client, "student@example.com", "securepass")
    response = client.get(
        "/courses/academic-ai-fundamentals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    course = response.json()
    assert course["title"] == "AI Fundamentals"
    assert course["module_type"] == "academic"
    assert len(course["lessons"]) == 3


def test_view_course_not_found(client):
    token = register_and_login(client, "student@example.com", "securepass")
    response = client.get(
        "/courses/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_passwords_are_hashed(client):
    from app.database import db_session

    client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass"},
    )
    with db_session() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("student@example.com",),
        ).fetchone()
    assert row["password_hash"] != "securepass"
    assert row["password_hash"].startswith("$2")
```
