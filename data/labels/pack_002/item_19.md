# item_19

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
`item_19`. Answer from the code alone; do not run the tools.

---

## The code

### `app.py`

```
"""Agent Education System — minimal API per spec.

Features:
  - auth.register, auth.login
  - course.list, course.view
  - training.module.corporate, training.module.academic

Governance:
  - no PII stored (only email + bcrypt-hashed password)
  - passwords hashed with bcrypt
  - no external API calls
"""
from __future__ import annotations

import re
import secrets
from http import HTTPStatus

import bcrypt
from flask import Flask, jsonify, request

from courses import COURSES

app = Flask(__name__)

_users: dict[str, bytes] = {}
_sessions: dict[str, str] = {}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _auth_user() -> str | None:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return _sessions.get(token)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not EMAIL_RE.match(email) or len(password) < 8:
        return jsonify(error="invalid email or password"), HTTPStatus.BAD_REQUEST
    if email in _users:
        return jsonify(error="user exists"), HTTPStatus.CONFLICT
    _users[email] = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    return jsonify(email=email), HTTPStatus.CREATED


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    stored = _users.get(email)
    if not stored or not bcrypt.checkpw(password.encode(), stored):
        return jsonify(error="invalid credentials"), HTTPStatus.UNAUTHORIZED
    token = secrets.token_urlsafe(32)
    _sessions[token] = email
    return jsonify(token=token)


@app.get("/courses")
def list_courses():
    if not _auth_user():
        return jsonify(error="unauthorized"), HTTPStatus.UNAUTHORIZED
    return jsonify(courses=[{"id": c["id"], "title": c["title"], "type": c["type"]} for c in COURSES])


@app.get("/courses/<course_id>")
def view_course(course_id: str):
    if not _auth_user():
        return jsonify(error="unauthorized"), HTTPStatus.UNAUTHORIZED
    course = next((c for c in COURSES if c["id"] == course_id), None)
    if not course:
        return jsonify(error="not found"), HTTPStatus.NOT_FOUND
    return jsonify(course)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

### `courses.py`

```
"""Mock course catalog: one corporate, one academic module."""

COURSES = [
    {
        "id": "tesco-standards",
        "type": "corporate",
        "title": "Tesco Operational Standards",
        "lessons": [
            {"id": 1, "title": "Customer Service Principles",
             "body": "Greet every customer; resolve issues at first point of contact."},
            {"id": 2, "title": "Food Safety & Hygiene",
             "body": "Maintain cold chain; follow date-rotation (FIFO) on shelves."},
            {"id": 3, "title": "Health & Safety on the Shop Floor",
             "body": "Report spills immediately; use correct lifting technique."},
        ],
    },
    {
        "id": "ai-fundamentals",
        "type": "academic",
        "title": "AI Fundamentals",
        "lessons": [
            {"id": 1, "title": "What is Machine Learning?",
             "body": "Systems that learn patterns from data instead of explicit rules."},
            {"id": 2, "title": "Supervised vs Unsupervised Learning",
             "body": "Labeled targets vs. structure discovery in unlabeled data."},
            {"id": 3, "title": "Neural Networks Overview",
             "body": "Layered function approximators trained via gradient descent."},
        ],
    },
]
```

### `test_app.py`

```
import pytest
from app import app, _users, _sessions


@pytest.fixture
def client():
    _users.clear()
    _sessions.clear()
    app.testing = True
    return app.test_client()


def _register(c, email="alice@example.com", password="hunter2hunter"):
    return c.post("/auth/register", json={"email": email, "password": password})


def _login(c, email="alice@example.com", password="hunter2hunter"):
    r = c.post("/auth/login", json={"email": email, "password": password})
    return r, r.get_json().get("token") if r.status_code == 200 else None


def test_register_creates_user(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.get_json()["email"] == "alice@example.com"


def test_register_rejects_bad_email(client):
    r = client.post("/auth/register", json={"email": "nope", "password": "longenough"})
    assert r.status_code == 400


def test_register_rejects_short_password(client):
    r = client.post("/auth/register", json={"email": "a@b.co", "password": "short"})
    assert r.status_code == 400


def test_register_duplicate(client):
    _register(client)
    assert _register(client).status_code == 409


def test_password_is_hashed(client):
    _register(client)
    stored = _users["alice@example.com"]
    assert stored != b"hunter2hunter"
    assert stored.startswith(b"$2")  # bcrypt prefix


def test_login_success_returns_token(client):
    _register(client)
    r, token = _login(client)
    assert r.status_code == 200
    assert token and len(token) > 20


def test_login_wrong_password(client):
    _register(client)
    r = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrongwrong"})
    assert r.status_code == 401


def test_courses_require_auth(client):
    assert client.get("/courses").status_code == 401
    assert client.get("/courses/ai-fundamentals").status_code == 401


def test_list_courses(client):
    _register(client)
    _, token = _login(client)
    r = client.get("/courses", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    ids = {c["id"] for c in r.get_json()["courses"]}
    assert {"tesco-standards", "ai-fundamentals"} <= ids


def test_view_course_with_lessons(client):
    _register(client)
    _, token = _login(client)
    r = client.get("/courses/ai-fundamentals", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["type"] == "academic"
    assert len(body["lessons"]) >= 1


def test_view_unknown_course(client):
    _register(client)
    _, token = _login(client)
    r = client.get("/courses/nope", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_corporate_module_present(client):
    _register(client)
    _, token = _login(client)
    r = client.get("/courses/tesco-standards", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["type"] == "corporate"
```
