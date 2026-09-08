# item_06

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

Write your number in `labels_rater<N>.csv` on the row for `item_06`.

---

## The code (21 files, 743 lines)

### `README.md`

```md
# Agent Education System (v1.0.0)

REST API for student registration, authentication, course catalog, and mock training modules.

## Features

| ID | Endpoint | Description |
|----|----------|-------------|
| `auth.register` | `POST /auth/register` | Create account (synthetic test email + password) |
| `auth.login` | `POST /auth/login` | Log in and receive a session token |
| `course.list` | `GET /courses` | List available courses (Bearer token required) |
| `course.view` | `GET /courses/{slug}` | View course and lessons |
| `training.module.corporate` | `GET /training/modules/corporate` | Tesco retail standards mock module |
| `training.module.academic` | `GET /training/modules/academic` | AI fundamentals mock module |

## Governance

- **no_pii**: Only synthetic emails on `*.test` domains are accepted at registration. No names, phone numbers, or addresses are stored.
- **hashed_passwords**: Passwords are hashed with bcrypt before storage.
- **no_external_calls**: Application code makes no outbound HTTP calls; external API allowlist is empty.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

### Example flow

```bash
# Register (test email only)
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"student@student.test","password":"password123"}'

# Use session_token from response
export TOKEN="<session_token>"

curl -s http://127.0.0.1:8000/courses -H "Authorization: Bearer $TOKEN"
curl -s http://127.0.0.1:8000/training/modules/corporate -H "Authorization: Bearer $TOKEN"
```

## Tests

```bash
pytest
```

## Sonar

Project key: `dominicrume_NEW-enterprise-ai-code-quality-auditor` (see `sonar-project.properties`).
```

### `app/__init__.py`

```py
"""Agent education system API."""
```

### `app/config.py`

```py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "agent_education_system"
    app_version: str = "1.0.0"
    database_url: str = "sqlite:///./education.db"
    jwt_secret: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24


settings = Settings()
```

### `app/database.py`

```py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### `app/deps.py`

```py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_session_token, get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header.",
        )
    try:
        payload = decode_session_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        ) from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user
```

### `app/governance.py`

```py
"""Governance guardrails: no PII beyond login email, no external API calls."""

import re

# Synthetic / test email domains only — no real PII storage policy.
ALLOWED_EMAIL_DOMAIN_SUFFIXES = (
    "@example.test",
    "@student.test",
    "@learn.test",
)

_REAL_NAME_PATTERN = re.compile(
    r"\b(phone|ssn|social.security|date.of.birth|dob|address|passport)\b",
    re.IGNORECASE,
)


def validate_registration_email(email: str) -> None:
    normalized = email.strip().lower()
    if not any(normalized.endswith(suffix) for suffix in ALLOWED_EMAIL_DOMAIN_SUFFIXES):
        raise ValueError(
            "Email must use a synthetic test domain "
            "(example.test, student.test, or learn.test). Real PII is not permitted."
        )


def reject_pii_in_text(text: str, field_name: str) -> None:
    if _REAL_NAME_PATTERN.search(text):
        raise ValueError(f"{field_name} must not contain personally identifiable information.")
```

### `app/main.py`

```py
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import auth, courses, training
from app.seed import seed_courses


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_courses(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(training.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
```

### `app/models.py`

```py
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    module_type: Mapped[str] = mapped_column(String(32))

    lessons: Mapped[list["Lesson"]] = relationship(back_populates="course", order_by="Lesson.order_index")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column()

    course: Mapped["Course"] = relationship(back_populates="lessons")
```

### `app/routers/__init__.py`

```py

```

### `app/routers/auth.py`

```py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.governance import validate_registration_email
from app.models import User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.security import create_session_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        validate_registration_email(body.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id, user.email)
    return AuthResponse(session_token=token)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_session_token(user.id, user.email)
    return AuthResponse(session_token=token)
```

### `app/routers/courses.py`

```py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Course, User
from app.schemas import CourseDetail, CourseSummary

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummary])
def list_courses(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Course]:
    return db.query(Course).order_by(Course.id).all()


@router.get("/{slug}", response_model=CourseDetail)
def view_course(
    slug: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    course = (
        db.query(Course)
        .options(joinedload(Course.lessons))
        .filter(Course.slug == slug)
        .first()
    )
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
        )
    return course
```

### `app/routers/training.py`

```py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import Course, User
from app.schemas import LessonOut, TrainingModuleOut
from app.seed import ACADEMIC_SLUG, CORPORATE_SLUG

router = APIRouter(prefix="/training/modules", tags=["training"])


def _module_response(course: Course) -> TrainingModuleOut:
    return TrainingModuleOut(
        id=course.slug,
        title=course.title,
        description=course.description,
        module_type=course.module_type,
        lessons=[LessonOut.model_validate(lesson) for lesson in course.lessons],
    )


def _get_module_by_slug(db: Session, slug: str) -> Course:
    course = (
        db.query(Course)
        .options(joinedload(Course.lessons))
        .filter(Course.slug == slug)
        .first()
    )
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training module not found.",
        )
    return course


@router.get("/corporate", response_model=TrainingModuleOut)
def corporate_module(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingModuleOut:
    """Mock corporate training module (Tesco retail standards)."""
    course = _get_module_by_slug(db, CORPORATE_SLUG)
    return _module_response(course)


@router.get("/academic", response_model=TrainingModuleOut)
def academic_module(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingModuleOut:
    """Mock academic training module (AI fundamentals)."""
    course = _get_module_by_slug(db, ACADEMIC_SLUG)
    return _module_response(course)
```

### `app/schemas.py`

```py
import re

from pydantic import BaseModel, Field, field_validator

_TEST_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _TEST_EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format.")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _TEST_EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format.")
        return normalized


class AuthResponse(BaseModel):
    session_token: str
    token_type: str = "bearer"


class LessonOut(BaseModel):
    id: int
    title: str
    content: str
    order_index: int

    model_config = {"from_attributes": True}


class CourseSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    module_type: str

    model_config = {"from_attributes": True}


class CourseDetail(CourseSummary):
    lessons: list[LessonOut]


class TrainingModuleOut(BaseModel):
    id: str
    title: str
    description: str
    module_type: str
    lessons: list[LessonOut]
```

### `app/security.py`

```py
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired session token.") from exc


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
```

### `app/seed.py`

```py
from sqlalchemy.orm import Session

from app.models import Course, Lesson

CORPORATE_SLUG = "tesco-standards"
ACADEMIC_SLUG = "ai-fundamentals"


def seed_courses(db: Session) -> None:
    if db.query(Course).count() > 0:
        return

    corporate = Course(
        slug=CORPORATE_SLUG,
        title="Tesco Retail Standards",
        description="Mock corporate training covering in-store safety, customer service, and compliance.",
        module_type="corporate",
    )
    academic = Course(
        slug=ACADEMIC_SLUG,
        title="AI Fundamentals",
        description="Mock academic module introducing machine learning concepts and responsible AI.",
        module_type="academic",
    )
    db.add_all([corporate, academic])
    db.flush()

    db.add_all(
        [
            Lesson(
                course_id=corporate.id,
                title="Health and Safety on the Shop Floor",
                content="Identify hazards, follow PPE guidance, and report incidents using store protocols.",
                order_index=1,
            ),
            Lesson(
                course_id=corporate.id,
                title="Customer Service Standards",
                content="Greet customers promptly, handle complaints with the LEARN framework, and escalate when needed.",
                order_index=2,
            ),
            Lesson(
                course_id=corporate.id,
                title="Stock and Freshness Compliance",
                content="Rotate dated products, maintain FIFO, and complete traceability checks for chilled goods.",
                order_index=3,
            ),
            Lesson(
                course_id=academic.id,
                title="What Is Machine Learning?",
                content="Supervised vs unsupervised learning, training data, and model evaluation basics.",
                order_index=1,
            ),
            Lesson(
                course_id=academic.id,
                title="Neural Networks Overview",
                content="Layers, activations, backpropagation intuition, and when deep models help.",
                order_index=2,
            ),
            Lesson(
                course_id=academic.id,
                title="Responsible AI Principles",
                content="Fairness, transparency, privacy, and human oversight in deployed systems.",
                order_index=3,
            ),
        ]
    )
    db.commit()
```

### `tests/__init__.py`

```py

```

### `tests/conftest.py`

```py
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret"

from app.database import Base, get_db
from app.main import app
from app.seed import seed_courses


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        db = TestingSession()
        seed_courses(db)
        db.close()
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": "learner@student.test", "password": "securepass1"},
    )
    assert response.status_code == 201
    token = response.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}
```

### `tests/test_auth.py`

```py
from fastapi.testclient import TestClient

from app.security import hash_password, verify_password


def test_register_and_login(client: TestClient) -> None:
    register = client.post(
        "/auth/register",
        json={"email": "newuser@example.test", "password": "password123"},
    )
    assert register.status_code == 201
    assert "session_token" in register.json()

    login = client.post(
        "/auth/login",
        json={"email": "newuser@example.test", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_register_rejects_non_test_email(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "real.person@gmail.com", "password": "password123"},
    )
    assert response.status_code == 400


def test_login_invalid_credentials(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "user@learn.test", "password": "password123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "user@learn.test", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_passwords_are_bcrypt_hashed() -> None:
    hashed = hash_password("password123")
    assert hashed.startswith("$2")
    assert verify_password("password123", hashed)
    assert not verify_password("wrong", hashed)
```

### `tests/test_courses.py`

```py
from fastapi.testclient import TestClient


def test_list_courses_requires_auth(client: TestClient) -> None:
    response = client.get("/courses")
    assert response.status_code == 401


def test_list_and_view_courses(client: TestClient, auth_headers: dict[str, str]) -> None:
    listed = client.get("/courses", headers=auth_headers)
    assert listed.status_code == 200
    courses = listed.json()
    assert len(courses) == 2
    slugs = {course["slug"] for course in courses}
    assert slugs == {"tesco-standards", "ai-fundamentals"}

    detail = client.get("/courses/tesco-standards", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["module_type"] == "corporate"
    assert len(body["lessons"]) == 3


def test_view_unknown_course(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/courses/unknown", headers=auth_headers)
    assert response.status_code == 404
```

### `tests/test_governance.py`

```py
import ast
from pathlib import Path

from app.governance import reject_pii_in_text, validate_registration_email


def test_validate_registration_email_accepts_test_domains() -> None:
    validate_registration_email("user@student.test")


def test_validate_registration_email_rejects_real_domains() -> None:
    try:
        validate_registration_email("user@company.com")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_reject_pii_in_text() -> None:
    try:
        reject_pii_in_text("my phone number is 555", "note")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_no_external_http_calls_in_app_code() -> None:
    """Governance: external API allowlist is empty — app must not import HTTP clients."""
    app_root = Path(__file__).resolve().parents[1] / "app"
    forbidden_imports = {"requests", "httpx", "aiohttp", "urllib.request"}
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_imports, (
                        f"Forbidden external HTTP import in {path}: {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_imports, (
                    f"Forbidden external HTTP import in {path}: {node.module}"
                )
```

### `tests/test_training.py`

```py
from fastapi.testclient import TestClient


def test_corporate_module(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/training/modules/corporate", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "tesco-standards"
    assert body["module_type"] == "corporate"
    assert "Tesco" in body["title"]
    assert len(body["lessons"]) >= 1


def test_academic_module(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/training/modules/academic", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ai-fundamentals"
    assert body["module_type"] == "academic"
    assert "AI" in body["title"]
    assert len(body["lessons"]) >= 1


def test_training_requires_auth(client: TestClient) -> None:
    assert client.get("/training/modules/corporate").status_code == 401
    assert client.get("/training/modules/academic").status_code == 401
```
