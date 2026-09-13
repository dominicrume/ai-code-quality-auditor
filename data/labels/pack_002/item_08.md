# item_08

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
`item_08`. Answer from the code alone; do not run the tools.

---

## The code

### `app.py`

```
"""Agent Education System — minimal Flask app.

Governance:
- No PII stored (only email + bcrypt password hash).
- Passwords hashed with bcrypt.
- No external API calls.
"""
import secrets
from functools import wraps

import bcrypt
from flask import Flask, jsonify, request

from courses import COURSES

app = Flask(__name__)

# In-memory stores (demo only).
_users: dict[str, bytes] = {}        # email -> bcrypt hash
_tokens: dict[str, str] = {}         # token -> email


def _auth_email() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return _tokens.get(header[7:])


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        email = _auth_email()
        if not email:
            return jsonify({"error": "unauthorized"}), 401
        return fn(email, *args, **kwargs)
    return wrapper


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if email in _users:
        return jsonify({"error": "already registered"}), 409
    _users[email] = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    return jsonify({"status": "registered", "email": email}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    stored = _users.get(email)
    if not stored or not bcrypt.checkpw(password.encode(), stored):
        return jsonify({"error": "invalid credentials"}), 401
    token = secrets.token_urlsafe(32)
    _tokens[token] = email
    return jsonify({"token": token})


@app.get("/courses")
@require_auth
def list_courses(_email):
    return jsonify([
        {"id": c["id"], "title": c["title"], "type": c["type"]}
        for c in COURSES.values()
    ])


@app.get("/courses/<course_id>")
@require_auth
def view_course(_email, course_id):
    course = COURSES.get(course_id)
    if not course:
        return jsonify({"error": "not found"}), 404
    return jsonify(course)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

### `courses.py`

```
"""Mock training modules. No PII; content is illustrative only."""

COURSES = {
    "corp-tesco-standards": {
        "id": "corp-tesco-standards",
        "title": "Corporate Training: Tesco Operational Standards (Mock)",
        "type": "corporate",
        "lessons": [
            {"id": 1, "title": "Customer Service Principles",
             "body": "Greet every customer; resolve issues at first contact."},
            {"id": 2, "title": "Health & Safety on the Shop Floor",
             "body": "Spill protocols, PPE, and incident reporting basics."},
            {"id": 3, "title": "Stock Rotation (FIFO)",
             "body": "First-in, first-out to minimise waste and ensure freshness."},
        ],
    },
    "acad-ai-fundamentals": {
        "id": "acad-ai-fundamentals",
        "title": "Academic Module: AI Fundamentals (Mock)",
        "type": "academic",
        "lessons": [
            {"id": 1, "title": "What is Machine Learning?",
             "body": "Learning patterns from data versus explicit programming."},
            {"id": 2, "title": "Supervised vs Unsupervised Learning",
             "body": "Labelled training data versus structure discovery."},
            {"id": 3, "title": "Neural Networks in One Page",
             "body": "Layers, weights, activations, and gradient descent."},
        ],
    },
}
```

### `test_app.py`

```
import pytest
from app import app, _users, _tokens


@pytest.fixture
def client():
    _users.clear()
    _tokens.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _register(client, email="stud@example.test", password="pw-correct-horse"):
    return client.post("/auth/register", json={"email": email, "password": password})


def _login(client, email="stud@example.test", password="pw-correct-horse"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_creates_user(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.get_json()["email"] == "stud@example.test"


def test_register_rejects_missing_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400


def test_register_rejects_duplicate(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_returns_token(client):
    _register(client)
    r = _login(client)
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_rejects_bad_password(client):
    _register(client)
    assert _login(client, password="wrong").status_code == 401


def test_courses_require_auth(client):
    assert client.get("/courses").status_code == 401


def test_list_courses(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get("/courses", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    ids = {c["id"] for c in r.get_json()}
    assert {"corp-tesco-standards", "acad-ai-fundamentals"} <= ids


def test_view_course_with_lessons(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get(
        "/courses/acad-ai-fundamentals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["type"] == "academic"
    assert len(body["lessons"]) >= 1


def test_view_unknown_course_404(client):
    _register(client)
    token = _login(client).get_json()["token"]
    r = client.get("/courses/nope", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_password_is_hashed_not_plaintext(client):
    _register(client, password="pw-correct-horse")
    stored = _users["stud@example.test"]
    assert isinstance(stored, bytes)
    assert b"pw-correct-horse" not in stored
```
