"""User accounts: sign up, log in, log out.

How it works:
- A user signs up with first name, last name, password, and an email and/or phone.
- Passwords are never stored as plain text. We store a hash (werkzeug.security).
- They log in with their email OR phone number plus password.
- After login the server gives them a random token.
- The frontend sends that token with every request:  Authorization: Bearer <token>
- @login_required checks the token and puts the user in g.user.

Prototype note: users and tokens live in memory, so they reset when the server
restarts. Next step: store them in the database.
"""
import re
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

users = {}            # user_id -> user dict
users_by_email = {}   # email -> user_id
users_by_phone = {}   # phone -> user_id
tokens = {}           # token -> user_id

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{8,15}$")   # e.g. +353871234567 or +919876543210
MIN_PASSWORD_LENGTH = 8


def clean_phone(phone):
    """Remove spaces, dashes and brackets: '+353 87 123 4567' -> '+353871234567'."""
    return re.sub(r"[\s\-()]", "", phone or "")


def public_user(user):
    """The user data that is safe to send to the frontend (no password hash)."""
    return {k: user[k] for k in ("id", "first_name", "last_name", "email", "phone", "created_at")}


def login_required(view):
    """Decorator: only lets the request through if it has a valid token."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        user_id = tokens.get(token)
        if not user_id:
            return jsonify({"error": "Please log in first."}), 401
        g.user = users[user_id]
        g.token = token
        return view(*args, **kwargs)
    return wrapper


def new_session(user, status_code=200):
    token = secrets.token_urlsafe(32)
    tokens[token] = user["id"]
    response = jsonify({"token": token, "user": public_user(user)})
    response.status_code = status_code
    return response


@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    first_name = (body.get("first_name") or "").strip()
    last_name = (body.get("last_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    phone = clean_phone(body.get("phone"))
    password = body.get("password") or ""

    # ----- Validation -----
    if not first_name or not last_name:
        return jsonify({"error": "Please enter your first and last name."}), 400
    if len(first_name) > 50 or len(last_name) > 50:
        return jsonify({"error": "Names must be 50 characters or fewer."}), 400
    if not email and not phone:
        return jsonify({"error": "Enter an email address or a phone number."}), 400
    if email and not EMAIL_PATTERN.match(email):
        return jsonify({"error": "That email address doesn't look right."}), 400
    if phone and not PHONE_PATTERN.match(phone):
        return jsonify({"error": "Phone number must be 8–15 digits, e.g. +353 87 123 4567."}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters."}), 400
    if email and email in users_by_email:
        return jsonify({"error": "An account with this email already exists."}), 409
    if phone and phone in users_by_phone:
        return jsonify({"error": "An account with this phone number already exists."}), 409

    # ----- Create the user -----
    user = {
        "id": str(uuid.uuid4()),
        "first_name": first_name,
        "last_name": last_name,
        "email": email or None,
        "phone": phone or None,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users[user["id"]] = user
    if email:
        users_by_email[email] = user["id"]
    if phone:
        users_by_phone[phone] = user["id"]

    return new_session(user, status_code=201)


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    identifier = (body.get("identifier") or "").strip()   # email or phone
    password = body.get("password") or ""

    if "@" in identifier:
        user_id = users_by_email.get(identifier.lower())
    else:
        user_id = users_by_phone.get(clean_phone(identifier))
    user = users.get(user_id)

    # Same message for "no such user" and "wrong password", so attackers can't
    # find out which accounts exist.
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Wrong email/phone or password."}), 401

    return new_session(user)


@auth_bp.post("/logout")
@login_required
def logout():
    tokens.pop(g.token, None)
    return jsonify({"message": "Logged out."})


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(public_user(g.user))
