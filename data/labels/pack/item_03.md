# item_03

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

Write your number in `labels_rater<N>.csv` on the row for `item_03`.

---

## The code (2 files, 172 lines)

### `app.py`

```py
import os
import secrets
import bcrypt
from flask import Flask, request, jsonify

app = Flask(__name__)

USERS = {}
SESSIONS = {}

COURSES = {
    "corp-tesco-001": {
        "id": "corp-tesco-001",
        "type": "corporate",
        "title": "Tesco Standards Training",
        "description": "Mock corporate-training module covering Tesco operational standards.",
        "lessons": [
            {"id": "l1", "title": "Customer Service Standards",
             "content": "Greet every customer; follow the 1-metre rule; resolve issues at first contact."},
            {"id": "l2", "title": "Health & Safety Basics",
             "content": "Spot hazards, report spills, follow manual-handling guidance."},
            {"id": "l3", "title": "Food Hygiene",
             "content": "Temperature controls, allergen labelling, FIFO stock rotation."},
        ],
    },
    "acad-ai-101": {
        "id": "acad-ai-101",
        "type": "academic",
        "title": "AI Fundamentals",
        "description": "Mock academic module introducing artificial intelligence concepts.",
        "lessons": [
            {"id": "l1", "title": "What is AI?",
             "content": "Symbolic vs statistical AI; narrow vs general intelligence."},
            {"id": "l2", "title": "Machine Learning Basics",
             "content": "Supervised, unsupervised, reinforcement learning paradigms."},
            {"id": "l3", "title": "Neural Networks",
             "content": "Perceptrons, activation functions, backpropagation overview."},
        ],
    },
}


def _auth_user():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    return SESSIONS.get(token)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if email in USERS:
        return jsonify({"error": "user exists"}), 409
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    USERS[email] = {"email": email, "password_hash": pw_hash}
    return jsonify({"ok": True, "email": email}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = USERS.get(email)
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = email
    return jsonify({"token": token}), 200


@app.get("/courses")
def list_courses():
    if not _auth_user():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify([
        {"id": c["id"], "type": c["type"], "title": c["title"], "description": c["description"]}
        for c in COURSES.values()
    ])


@app.get("/courses/<course_id>")
def view_course(course_id):
    if not _auth_user():
        return jsonify({"error": "unauthorized"}), 401
    course = COURSES.get(course_id)
    if not course:
        return jsonify({"error": "not found"}), 404
    return jsonify(course)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
```

### `test_app.py`

```py
import pytest
from app import app, USERS, SESSIONS


@pytest.fixture
def client():
    USERS.clear()
    SESSIONS.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _register(client, email="a@example.test", password="pw12345"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email="a@example.test", password="pw12345"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_creates_user(client):
    r = _register(client)
    assert r.status_code == 201
    assert "a@example.test" in USERS
    assert USERS["a@example.test"]["password_hash"] != b"pw12345"


def test_register_requires_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400


def test_register_duplicate(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_returns_token(client):
    _register(client)
    r = _login(client)
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_bad_password(client):
    _register(client)
    assert _login(client, password="wrong").status_code == 401


def test_courses_require_auth(client):
    assert client.get("/courses").status_code == 401


def test_list_courses(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get("/courses", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.get_json()
    types = {c["type"] for c in data}
    assert "corporate" in types and "academic" in types


def test_view_course(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get("/courses/acad-ai-101", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.get_json()["lessons"]) >= 1


def test_view_course_missing(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get("/courses/nope", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
```
