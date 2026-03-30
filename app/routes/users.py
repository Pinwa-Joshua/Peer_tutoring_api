from flask import Blueprint, request, jsonify
from ..database import db
from ..models import User
from ..utils.auth import hash_password, verify_password
import jwt
import json
from pathlib import Path

users_bp = Blueprint("users", __name__)
JWT_SECRET = "supersecretkey"
STUDENT_EXTRAS_FILE = Path(__file__).resolve().parents[1] / "data" / "student_profile_extras.json"


def get_current_user_from_request():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split(" ")
    if len(parts) != 2:
        return None

    try:
        data = jwt.decode(parts[1], JWT_SECRET, algorithms=["HS256"])
        return data.get("user_id")
    except Exception:
        return None


def load_student_extras():
    if not STUDENT_EXTRAS_FILE.exists():
        return {}

    try:
        return json.loads(STUDENT_EXTRAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_student_extras(extras):
    STUDENT_EXTRAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STUDENT_EXTRAS_FILE.write_text(json.dumps(extras, indent=2), encoding="utf-8")


def get_student_extras(user_id):
    return load_student_extras().get(str(user_id), {})


@users_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "Email already exists"}), 400

    user = User(
        full_name=data["full_name"],
        email=data["email"],
        password_hash=hash_password(data["password"]),
        role=data["role"],
    )

    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered"}), 201


@users_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data["email"]).first()

    if not user or not verify_password(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({"message": "Use /api/auth/login for authentication"}), 200


@users_bp.route("/me", methods=["GET"])
def get_me():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    extras = get_student_extras(user.id)

    return jsonify({
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "photo": extras.get("photo", ""),
        "bio": extras.get("bio", ""),
        "university": extras.get("university", ""),
        "campus": extras.get("campus", ""),
        "year": extras.get("year", ""),
        "faculty": extras.get("faculty", ""),
        "subjects": extras.get("subjects", []),
        "preferred_format": extras.get("preferred_format", ""),
        "preferred_days": extras.get("preferred_days", []),
        "budget_min": extras.get("budget_min", ""),
        "budget_max": extras.get("budget_max", ""),
    }), 200


@users_bp.route("/update-profile", methods=["OPTIONS", "PUT"])
def update_profile():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    data = request.get_json() or {}
    full_name = (data.get("full_name") or "").strip()

    if full_name:
        user.full_name = full_name

    extras = load_student_extras()
    current_extras = extras.get(str(user.id), {})

    current_extras.update({
        "photo": data.get("photo") or "",
        "bio": (data.get("bio") or "").strip(),
        "university": (data.get("university") or "").strip(),
        "campus": (data.get("campus") or "").strip(),
        "year": (data.get("year") or "").strip(),
        "faculty": (data.get("faculty") or "").strip(),
        "subjects": data.get("subjects") if isinstance(data.get("subjects"), list) else current_extras.get("subjects", []),
        "preferred_format": (data.get("preferred_format") or "").strip(),
        "preferred_days": data.get("preferred_days") if isinstance(data.get("preferred_days"), list) else current_extras.get("preferred_days", []),
        "budget_min": str(data.get("budget_min") or ""),
        "budget_max": str(data.get("budget_max") or ""),
    })
    extras[str(user.id)] = current_extras
    save_student_extras(extras)

    db.session.commit()

    return jsonify({
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "photo": current_extras.get("photo", ""),
            "bio": current_extras.get("bio", ""),
            "university": current_extras.get("university", ""),
            "campus": current_extras.get("campus", ""),
            "year": current_extras.get("year", ""),
            "faculty": current_extras.get("faculty", ""),
            "subjects": current_extras.get("subjects", []),
            "preferred_format": current_extras.get("preferred_format", ""),
            "preferred_days": current_extras.get("preferred_days", []),
            "budget_min": current_extras.get("budget_min", ""),
            "budget_max": current_extras.get("budget_max", ""),
        }
    }), 200
