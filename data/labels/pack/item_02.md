# item_02

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

Write your number in `labels_rater<N>.csv` on the row for `item_02`.

---

## The code (2 files, 190 lines)

### `app.py`

```py
"""Agent Education System - minimal Flask app.

Features: auth.register, auth.login, course.list, course.view,
training.module.corporate, training.module.academic.

Governance: no PII stored, passwords hashed (bcrypt), no external API calls.
"""
from __future__ import annotations

import secrets
from functools import wraps
from http import HTTPStatus

import bcrypt
from flask import Flask, g, jsonify, request


def create_app() -> Flask:
    app = Flask(__name__)

    # In-memory stores. Email is treated as an account identifier only;
    # the spec forbids storing real PII, so deployments must surface a
    # synthetic/opaque identifier instead of a real address.
    users: dict[str, bytes] = {}
    tokens: dict[str, str] = {}

    courses = _seed_courses()

    def auth_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="missing token"), HTTPStatus.UNAUTHORIZED
            token = header.removeprefix("Bearer ").strip()
            user = tokens.get(token)
            if user is None:
                return jsonify(error="invalid token"), HTTPStatus.UNAUTHORIZED
            g.user = user
            return view(*args, **kwargs)

        return wrapper

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not email or not password:
            return jsonify(error="email and password required"), HTTPStatus.BAD_REQUEST
        if email in users:
            return jsonify(error="account exists"), HTTPStatus.CONFLICT
        users[email] = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        return jsonify(status="registered"), HTTPStatus.CREATED

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        hashed = users.get(email)
        if hashed is None or not bcrypt.checkpw(password.encode(), hashed):
            return jsonify(error="invalid credentials"), HTTPStatus.UNAUTHORIZED
        token = secrets.token_urlsafe(32)
        tokens[token] = email
        return jsonify(token=token)

    @app.get("/courses")
    @auth_required
    def list_courses():
        return jsonify(
            courses=[
                {"id": c["id"], "title": c["title"], "track": c["track"]}
                for c in courses.values()
            ]
        )

    @app.get("/courses/<course_id>")
    @auth_required
    def view_course(course_id: str):
        course = courses.get(course_id)
        if course is None:
            return jsonify(error="not found"), HTTPStatus.NOT_FOUND
        return jsonify(course)

    return app


def _seed_courses() -> dict[str, dict]:
    corporate = {
        "id": "tesco-standards",
        "track": "corporate",
        "title": "Tesco Operational Standards (Mock)",
        "lessons": [
            {"id": 1, "title": "Customer-first values", "body": "Mock lesson content."},
            {"id": 2, "title": "Food safety basics", "body": "Mock lesson content."},
            {"id": 3, "title": "Stock rotation procedure", "body": "Mock lesson content."},
        ],
    }
    academic = {
        "id": "ai-fundamentals",
        "track": "academic",
        "title": "AI Fundamentals (Mock)",
        "lessons": [
            {"id": 1, "title": "What is an agent?", "body": "Mock lesson content."},
            {"id": 2, "title": "Supervised learning", "body": "Mock lesson content."},
            {"id": 3, "title": "Evaluation and governance", "body": "Mock lesson content."},
        ],
    }
    return {corporate["id"]: corporate, academic["id"]: academic}


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

### `tests/test_app.py`

```py
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def _register_and_login(client, email="student@example.test", password="hunter2!"):
    client.post("/auth/register", json={"email": email, "password": password})
    rv = client.post("/auth/login", json={"email": email, "password": password})
    return rv.get_json()["token"]


def test_register_requires_credentials(client):
    rv = client.post("/auth/register", json={})
    assert rv.status_code == 400


def test_register_then_login_returns_token(client):
    token = _register_and_login(client)
    assert isinstance(token, str) and len(token) > 20


def test_login_rejects_wrong_password(client):
    client.post("/auth/register", json={"email": "a@b.test", "password": "right"})
    rv = client.post("/auth/login", json={"email": "a@b.test", "password": "wrong"})
    assert rv.status_code == 401


def test_courses_require_auth(client):
    assert client.get("/courses").status_code == 401


def test_list_courses(client):
    token = _register_and_login(client)
    rv = client.get("/courses", headers={"Authorization": f"Bearer {token}"})
    assert rv.status_code == 200
    tracks = {c["track"] for c in rv.get_json()["courses"]}
    assert tracks == {"corporate", "academic"}


def test_view_course_includes_lessons(client):
    token = _register_and_login(client)
    rv = client.get(
        "/courses/ai-fundamentals", headers={"Authorization": f"Bearer {token}"}
    )
    assert rv.status_code == 200
    assert len(rv.get_json()["lessons"]) >= 1


def test_view_unknown_course(client):
    token = _register_and_login(client)
    rv = client.get(
        "/courses/nope", headers={"Authorization": f"Bearer {token}"}
    )
    assert rv.status_code == 404


def test_password_is_hashed_not_stored_plain(client):
    # Hashes are bcrypt and never equal the plaintext.
    import app as app_module

    fresh = app_module.create_app()
    c = fresh.test_client()
    c.post("/auth/register", json={"email": "x@y.test", "password": "plaintext"})
    # Inspect via login round-trip (we have no direct accessor by design).
    assert c.post("/auth/login", json={"email": "x@y.test", "password": "plaintext"}).status_code == 200
    assert c.post("/auth/login", json={"email": "x@y.test", "password": "PLAINTEXT"}).status_code == 401
```
