# item_05

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

Write your number in `labels_rater<N>.csv` on the row for `item_05`.

---

## The code (19 files, 593 lines)

### `README.md`

```md
# agent_education_system (v1.0.0)

Enterprise agent education API with student authentication, course catalog, and mock training modules.

## Features

| ID | Endpoint | Description |
|----|----------|-------------|
| `auth.register` | `POST /auth/register` | Create account with email and password |
| `auth.login` | `POST /auth/login` | Log in and receive a session token (JWT) |
| `course.list` | `GET /courses` | List available courses (Bearer auth) |
| `course.view` | `GET /courses/{course_id}` | View course and lessons (Bearer auth) |
| `training.module.corporate` | `GET /training/corporate` | Mock Tesco retail standards module |
| `training.module.academic` | `GET /training/academic` | Mock AI fundamentals module |

## Governance

- **no_pii**: Only synthetic `@example.com` emails are used in tests; no real PII is seeded.
- **hashed_passwords**: Passwords stored with bcrypt.
- **no_external_calls**: No outbound HTTP; empty external API allowlist.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -v
```

## SonarQube

Project key: `dominicrume_NEW-enterprise-ai-code-quality-auditor` (see `sonar-project.properties`).
```

### `app/__init__.py`

```py
"""Agent education system application package."""
```

### `app/auth_service.py`

```py
from app.database import get_connection
from app.security import hash_password, verify_password


class AuthError(Exception):
    pass


class UserExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


def register_user(email: str, password: str) -> int:
    password_hash = hash_password(password)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email.lower(), password_hash),
            )
            return int(cursor.lastrowid)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise UserExistsError("Email already registered") from exc
        raise


def authenticate_user(email: str, password: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        raise InvalidCredentialsError("Invalid email or password")
    return int(row["id"])
```

### `app/config.py`

```py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    database_path: str = "data/education.db"


settings = Settings()
```

### `app/database.py`

```py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _db_path() -> Path:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
```

### `app/dependencies.py`

```py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security import decode_session_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_session_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return {"user_id": int(payload["sub"]), "email": payload["email"]}
```

### `app/main.py`

```py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import auth, courses, training

APP_NAME = "agent_education_system"
APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Enterprise agent education platform with auth, courses, and training modules.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(training.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "name": APP_NAME, "version": APP_VERSION}
```

### `app/models.py`

```py
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    session_token: str
    token_type: str = "bearer"


class Lesson(BaseModel):
    id: str
    title: str
    order: int
    content_summary: str


class CourseSummary(BaseModel):
    id: str
    title: str
    description: str
    lesson_count: int


class CourseDetail(BaseModel):
    id: str
    title: str
    description: str
    lessons: list[Lesson]


class TrainingLesson(BaseModel):
    id: str
    title: str
    order: int
    content: str


class TrainingModule(BaseModel):
    id: str
    type: str
    title: str
    description: str
    lessons: list[TrainingLesson]
```

### `app/routers/__init__.py`

```py
"""API route modules."""
```

### `app/routers/auth.py`

```py
from fastapi import APIRouter, HTTPException, status

from app.auth_service import (
    InvalidCredentialsError,
    UserExistsError,
    authenticate_user,
    register_user,
)
from app.models import AuthResponse, LoginRequest, RegisterRequest
from app.security import create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest) -> AuthResponse:
    try:
        user_id = register_user(body.email, body.password)
    except UserExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    token = create_session_token(user_id, body.email.lower())
    return AuthResponse(session_token=token)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    try:
        user_id = authenticate_user(body.email, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    token = create_session_token(user_id, body.email.lower())
    return AuthResponse(session_token=token)
```

### `app/routers/courses.py`

```py
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models import CourseDetail, CourseSummary
from app.seed_data import get_course, list_course_summaries

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummary])
def list_courses(_user: dict = Depends(get_current_user)) -> list[CourseSummary]:
    return list_course_summaries()


@router.get("/{course_id}", response_model=CourseDetail)
def view_course(
    course_id: str,
    _user: dict = Depends(get_current_user),
) -> CourseDetail:
    course = get_course(course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course
```

### `app/routers/training.py`

```py
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models import TrainingModule
from app.seed_data import ACADEMIC_MODULE, CORPORATE_MODULE

router = APIRouter(prefix="/training", tags=["training"])


@router.get("/corporate", response_model=TrainingModule)
def corporate_module(_user: dict = Depends(get_current_user)) -> TrainingModule:
    return CORPORATE_MODULE


@router.get("/academic", response_model=TrainingModule)
def academic_module(_user: dict = Depends(get_current_user)) -> TrainingModule:
    return ACADEMIC_MODULE
```

### `app/security.py`

```py
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_token(user_id: int, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
```

### `app/seed_data.py`

```py
from app.models import CourseDetail, CourseSummary, Lesson, TrainingLesson, TrainingModule

COURSES: list[CourseDetail] = [
    CourseDetail(
        id="course-intro-platform",
        title="Platform Orientation",
        description="Learn how to navigate the agent education system.",
        lessons=[
            Lesson(
                id="lesson-welcome",
                title="Welcome",
                order=1,
                content_summary="Overview of learning paths and assessments.",
            ),
            Lesson(
                id="lesson-dashboard",
                title="Your Dashboard",
                order=2,
                content_summary="Track progress across corporate and academic modules.",
            ),
        ],
    ),
    CourseDetail(
        id="course-agent-basics",
        title="Agent Development Basics",
        description="Foundational concepts for building reliable agents.",
        lessons=[
            Lesson(
                id="lesson-tools",
                title="Tools and Context",
                order=1,
                content_summary="How agents use tools within governance boundaries.",
            ),
            Lesson(
                id="lesson-evals",
                title="Evaluation Patterns",
                order=2,
                content_summary="Measuring agent quality with structured test cases.",
            ),
        ],
    ),
]

CORPORATE_MODULE = TrainingModule(
    id="training-corporate-tesco-standards",
    type="corporate",
    title="Tesco Retail Standards (Mock)",
    description="Mock corporate training covering in-store standards and compliance.",
    lessons=[
        TrainingLesson(
            id="corp-lesson-1",
            title="Customer Service Standards",
            order=1,
            content="Mock content: greet customers promptly and maintain aisle standards.",
        ),
        TrainingLesson(
            id="corp-lesson-2",
            title="Health and Safety Basics",
            order=2,
            content="Mock content: report spills immediately and follow signage protocols.",
        ),
        TrainingLesson(
            id="corp-lesson-3",
            title="Stock Handling",
            order=3,
            content="Mock content: rotate perishable stock and verify use-by dates.",
        ),
    ],
)

ACADEMIC_MODULE = TrainingModule(
    id="training-academic-ai-fundamentals",
    type="academic",
    title="AI Fundamentals (Mock)",
    description="Mock academic module introducing core AI and ML concepts.",
    lessons=[
        TrainingLesson(
            id="acad-lesson-1",
            title="What Is Machine Learning?",
            order=1,
            content="Mock content: supervised vs unsupervised learning with simple examples.",
        ),
        TrainingLesson(
            id="acad-lesson-2",
            title="Neural Networks Overview",
            order=2,
            content="Mock content: layers, weights, and how models learn from data.",
        ),
        TrainingLesson(
            id="acad-lesson-3",
            title="Responsible AI",
            order=3,
            content="Mock content: bias, transparency, and governance in AI systems.",
        ),
    ],
)


def list_course_summaries() -> list[CourseSummary]:
    return [
        CourseSummary(
            id=course.id,
            title=course.title,
            description=course.description,
            lesson_count=len(course.lessons),
        )
        for course in COURSES
    ]


def get_course(course_id: str) -> CourseDetail | None:
    for course in COURSES:
        if course.id == course_id:
            return course
    return None
```

### `tests/__init__.py`

```py

```

### `tests/conftest.py`

```py
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = str(Path(__file__).parent / "test_education.db")
os.environ["JWT_SECRET"] = "test-secret"

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db_path = Path(os.environ["DATABASE_PATH"])
    if db_path.exists():
        db_path.unlink()
    init_db()
    yield
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": "student.demo@example.com", "password": "securepass1"},
    )
    assert response.status_code == 201
    token = response.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}
```

### `tests/test_auth.py`

```py
from app.security import hash_password, verify_password


def test_register_returns_session_token(client):
    response = client.post(
        "/auth/register",
        json={"email": "learner001@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "session_token" in body
    assert body["token_type"] == "bearer"


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_login_returns_session_token(client):
    email = "login.user@example.com"
    password = "password123"
    client.post("/auth/register", json={"email": email, "password": password})

    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    assert "session_token" in response.json()


def test_login_rejects_invalid_credentials(client):
    client.post(
        "/auth/register",
        json={"email": "valid@example.com", "password": "password123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "valid@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_passwords_are_hashed_not_stored_plaintext():
    hashed = hash_password("password123")
    assert hashed != "password123"
    assert verify_password("password123", hashed)
    assert not verify_password("wrong", hashed)
```

### `tests/test_courses.py`

```py
def test_list_courses_requires_auth(client):
    assert client.get("/courses").status_code == 403


def test_list_courses_returns_catalog(client, auth_headers):
    response = client.get("/courses", headers=auth_headers)
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) >= 2
    assert all("id" in c and "lesson_count" in c for c in courses)


def test_view_course_returns_lessons(client, auth_headers):
    list_response = client.get("/courses", headers=auth_headers)
    course_id = list_response.json()[0]["id"]

    response = client.get(f"/courses/{course_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == course_id
    assert len(body["lessons"]) >= 1


def test_view_course_not_found(client, auth_headers):
    response = client.get("/courses/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404
```

### `tests/test_training.py`

```py
def test_corporate_module_requires_auth(client):
    assert client.get("/training/corporate").status_code == 403


def test_corporate_module_content(client, auth_headers):
    response = client.get("/training/corporate", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "corporate"
    assert "Tesco" in body["title"]
    assert len(body["lessons"]) >= 1


def test_academic_module_content(client, auth_headers):
    response = client.get("/training/academic", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "academic"
    assert "AI" in body["title"]
    assert len(body["lessons"]) >= 1
```
