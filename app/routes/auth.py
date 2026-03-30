from flask import Blueprint, request, jsonify
from app.models import User, TutorProfile, db
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from .tutors import load_tutor_extras
from .users import get_student_extras
import json
import secrets
from pathlib import Path

auth_bp = Blueprint('auth', __name__)
JWT_SECRET = "supersecretkey"
PASSWORD_RESET_FILE = Path(__file__).resolve().parents[1] / "data" / "password_reset_tokens.json"


def load_password_resets():
    if not PASSWORD_RESET_FILE.exists():
        return {}

    try:
        return json.loads(PASSWORD_RESET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_password_resets(payload):
    PASSWORD_RESET_FILE.parent.mkdir(parents=True, exist_ok=True)
    PASSWORD_RESET_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"message": "Email already exists"}), 400
    
    new_user = User(
        full_name=data.get('full_name', ''),
        email=data.get('email'),
        role=data.get('role', 'tutee')
    )
    new_user.set_password(data.get('password'))
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.check_password(data.get('password')):
        token = jwt.encode({
            'user_id': user.id,
            'role': user.role,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, JWT_SECRET, algorithm="HS256")
        return jsonify({
            "message": "User logged in successfully",
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
        }), 200
    return jsonify({"message": "Invalid credentials"}), 401


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({"message": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "message": "If an account exists for that email, a reset link has been generated."
        }), 200

    token = secrets.token_urlsafe(32)
    resets = load_password_resets()
    resets[token] = {
        "user_id": user.id,
        "email": user.email,
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
    }
    save_password_resets(resets)

    return jsonify({
        "message": "Password reset link generated successfully.",
        "reset_token": token,
        "reset_link": f"http://localhost:5173/reset-password?token={token}",
        "expires_in_minutes": 60,
    }), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    token = (data.get('token') or '').strip()
    password = data.get('password') or ''

    if not token or not password:
        return jsonify({"message": "Token and password are required"}), 400

    if len(password) < 8:
        return jsonify({"message": "Password must be at least 8 characters"}), 400

    resets = load_password_resets()
    token_record = resets.get(token)
    if not token_record:
        return jsonify({"message": "Invalid or expired reset token"}), 400

    expires_at = token_record.get("expires_at")
    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except Exception:
        expires_dt = None

    if not expires_dt or expires_dt < datetime.utcnow():
        resets.pop(token, None)
        save_password_resets(resets)
        return jsonify({"message": "Invalid or expired reset token"}), 400

    user = User.query.get(token_record.get("user_id"))
    if not user:
        resets.pop(token, None)
        save_password_resets(resets)
        return jsonify({"message": "User not found"}), 404

    user.set_password(password)
    db.session.commit()

    resets.pop(token, None)
    save_password_resets(resets)

    return jsonify({"message": "Password reset successfully"}), 200

@auth_bp.route('/me', methods=['GET'])
def me():
    # Basic token validation implementation
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({"message": "Missing token"}), 401
    try:
        token = auth_header.split(" ")[1]
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_record = User.query.get(data['user_id'])
        user = dict(user_record.__dict__)
        user.pop('_sa_instance_state', None)
        user.pop('password_hash', None)

        profile = TutorProfile.query.filter_by(user_id=user_record.id).first()
        if profile:
            user['subjects'] = [s.strip() for s in (profile.subjects or '').split(',') if s.strip()]
            user['availability'] = profile.availability

        extras = load_tutor_extras().get(str(user_record.id), {})
        if extras:
            user['bio'] = extras.get('bio', '')
            user['university'] = extras.get('university', '')
            user['teaching_approach'] = extras.get('teaching_approach', '')
            user['profile_photo'] = extras.get('profile_photo', '')

        student_extras = get_student_extras(user_record.id)
        if student_extras:
            user['photo'] = student_extras.get('photo', '')
            user['bio'] = student_extras.get('bio', user.get('bio', ''))
            user['university'] = student_extras.get('university', user.get('university', ''))
            user['campus'] = student_extras.get('campus', '')
            user['year'] = student_extras.get('year', '')
            user['faculty'] = student_extras.get('faculty', '')
            user['subjects'] = student_extras.get('subjects', user.get('subjects', []))
            user['preferred_format'] = student_extras.get('preferred_format', '')
            user['preferred_days'] = student_extras.get('preferred_days', [])
            user['budget_min'] = student_extras.get('budget_min', '')
            user['budget_max'] = student_extras.get('budget_max', '')

        return jsonify(user), 200
    except Exception as e:
        return jsonify({"message": "Invalid/expired token"}), 401
    return jsonify({"message": "User info endpoint"}), 200
