# item_03

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
`item_03`. Answer from the code alone; do not run the tools.

---

## The code

### `app/__init__.py`

```
"""Agent Education System."""
```

### `app/config.py`

```
import os
import secrets

SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRE_HOURS = 24
DATABASE_PATH = os.environ.get("DATABASE_PATH", "education.db")
```

### `app/database.py`

```
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DATABASE_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
```

### `app/main.py`

```
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import auth, courses


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Agent Education System",
    version="1.0.0",
    description="Student registration, authentication, and course access API.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(courses.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

### `app/routes/__init__.py`

```

```

### `app/routes/auth.py`

```
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import get_db, utc_now_iso
from app.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.security import hash_password, verify_password
from app.sessions import create_session, get_user_id_for_token

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    user_id = get_user_id_for_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return user_id


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest) -> AuthResponse:
    password_hash = hash_password(body.password)
    created_at = utc_now_iso()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (body.email.lower(),),
        ).fetchone()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (body.email.lower(), password_hash, created_at),
        )
        user_id = cursor.lastrowid
    token = create_session(user_id)
    return AuthResponse(token=token, email=body.email.lower())


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (body.email.lower(),),
        ).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_session(row["id"])
    return AuthResponse(token=token, email=body.email.lower())
```

### `app/routes/courses.py`

```
from fastapi import APIRouter, Depends, HTTPException, status

from app.routes.auth import get_current_user_id
from app.schemas import CourseDetail, CourseSummary, Lesson

router = APIRouter(prefix="/courses", tags=["courses"])

CORPORATE_COURSE = CourseDetail(
    id="corporate-tesco-standards",
    title="Tesco Retail Standards",
    description=(
        "Corporate training module covering Tesco customer service, "
        "safety, and operational standards for store associates."
    ),
    module_type="corporate",
    lessons=[
        Lesson(
            id="tesco-1",
            title="Welcome and Brand Values",
            summary="Introduction to Tesco's Every Little Helps philosophy and team expectations.",
        ),
        Lesson(
            id="tesco-2",
            title="Customer Service Standards",
            summary="Greeting customers, handling enquiries, and resolving complaints professionally.",
        ),
        Lesson(
            id="tesco-3",
            title="Health, Safety, and Compliance",
            summary="Store safety procedures, food hygiene basics, and incident reporting.",
        ),
    ],
)

ACADEMIC_COURSE = CourseDetail(
    id="academic-ai-fundamentals",
    title="AI Fundamentals",
    description=(
        "Academic module introducing artificial intelligence concepts, "
        "machine learning workflows, and responsible AI practice."
    ),
    module_type="academic",
    lessons=[
        Lesson(
            id="ai-1",
            title="What Is Artificial Intelligence?",
            summary="Definitions, history, and common applications of AI in modern systems.",
        ),
        Lesson(
            id="ai-2",
            title="Machine Learning Basics",
            summary="Supervised vs unsupervised learning, datasets, and model evaluation.",
        ),
        Lesson(
            id="ai-3",
            title="Ethics and Responsible AI",
            summary="Bias, transparency, privacy considerations, and governance in AI systems.",
        ),
    ],
)

COURSES: dict[str, CourseDetail] = {
    CORPORATE_COURSE.id: CORPORATE_COURSE,
    ACADEMIC_COURSE.id: ACADEMIC_COURSE,
}


@router.get("", response_model=list[CourseSummary])
def list_courses(_user_id: int = Depends(get_current_user_id)) -> list[CourseSummary]:
    return [
        CourseSummary(
            id=course.id,
            title=course.title,
            description=course.description,
            module_type=course.module_type,
        )
        for course in COURSES.values()
    ]


@router.get("/{course_id}", response_model=CourseDetail)
def view_course(
    course_id: str,
    _user_id: int = Depends(get_current_user_id),
) -> CourseDetail:
    course = COURSES.get(course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course
```

### `app/schemas.py`

```
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    token: str
    email: str


class Lesson(BaseModel):
    id: str
    title: str
    summary: str


class CourseSummary(BaseModel):
    id: str
    title: str
    description: str
    module_type: str


class CourseDetail(CourseSummary):
    lessons: list[Lesson]
```

### `app/security.py`

```
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
```

### `app/sessions.py`

```
import secrets
from datetime import datetime, timedelta, timezone

from app.config import TOKEN_EXPIRE_HOURS
from app.database import get_db, utc_now_iso


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    ).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def get_user_id_for_token(token: str) -> int | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if row is None:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return None
    return row["user_id"]
```

### `tests/__init__.py`

```

```

### `tests/test_api.py`

```
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")

from app.database import get_db, init_db
from app.main import app
from app.security import verify_password


@pytest.fixture
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client
    if os.path.exists(os.environ["DATABASE_PATH"]):
        os.remove(os.environ["DATABASE_PATH"])


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass1"},
    )
    assert register_response.status_code == 201
    register_data = register_response.json()
    assert register_data["email"] == "student@example.com"
    assert register_data["token"]

    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("student@example.com",),
        ).fetchone()
    assert row is not None
    assert verify_password("securepass1", row["password_hash"])

    login_response = client.post(
        "/auth/login",
        json={"email": "student@example.com", "password": "securepass1"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["token"]


def test_register_duplicate_email(client: TestClient) -> None:
    payload = {"email": "student@example.com", "password": "securepass1"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_login_invalid_credentials(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass1"},
    )
    response = client.post(
        "/auth/login",
        json={"email": "student@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_course_list_requires_auth(client: TestClient) -> None:
    response = client.get("/courses")
    assert response.status_code == 401


def test_course_list_and_view(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass1"},
    )
    token = register_response.json()["token"]

    list_response = client.get("/courses", headers=auth_header(token))
    assert list_response.status_code == 200
    courses = list_response.json()
    assert len(courses) == 2
    module_types = {course["module_type"] for course in courses}
    assert module_types == {"corporate", "academic"}

    corporate = client.get(
        "/courses/corporate-tesco-standards",
        headers=auth_header(token),
    )
    assert corporate.status_code == 200
    corporate_data = corporate.json()
    assert corporate_data["title"] == "Tesco Retail Standards"
    assert len(corporate_data["lessons"]) == 3

    academic = client.get(
        "/courses/academic-ai-fundamentals",
        headers=auth_header(token),
    )
    assert academic.status_code == 200
    academic_data = academic.json()
    assert academic_data["title"] == "AI Fundamentals"
    assert len(academic_data["lessons"]) == 3


def test_course_view_not_found(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "student@example.com", "password": "securepass1"},
    )
    token = register_response.json()["token"]
    response = client.get("/courses/missing-course", headers=auth_header(token))
    assert response.status_code == 404
```
