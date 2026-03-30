from flask import Blueprint, request, jsonify
from app.database import db
from app.models import Session, User
import jwt
import json
from pathlib import Path

sessions_bp = Blueprint('sessions', __name__)
JWT_SECRET = "supersecretkey"
SESSION_DETAILS_FILE = Path(__file__).resolve().parents[1] / "data" / "session_details.json"


def get_current_user_from_request():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None

    parts = auth_header.split(" ")
    if len(parts) != 2:
        return None

    try:
        data = jwt.decode(parts[1], JWT_SECRET, algorithms=["HS256"])
        return data['user_id']
    except Exception:
        return None


def load_session_details():
    if not SESSION_DETAILS_FILE.exists():
        return {}

    try:
        return json.loads(SESSION_DETAILS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_session_details(details):
    SESSION_DETAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_DETAILS_FILE.write_text(json.dumps(details, indent=2), encoding="utf-8")


@sessions_bp.route('/', methods=['GET'])
def get_sessions():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    status = request.args.get('status')
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    if user.role == 'tutor':
        query = Session.query.filter_by(tutor_id=user_id)
    else:
        query = Session.query.filter_by(tutee_id=user_id)

    if status:
        query = query.filter_by(status=status)

    sessions = query.order_by(Session.created_at.desc()).all()
    details = load_session_details()
    results = []

    for session in sessions:
        other_user_id = session.tutee_id if user.role == 'tutor' else session.tutor_id
        other_user = User.query.get(other_user_id)
        session_detail = details.get(str(session.id), {})

        results.append({
            'id': session.id,
            'status': session.status,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'partner_id': other_user.id if other_user else None,
            'partner_name': other_user.full_name if other_user else 'Unknown',
            'partner_email': other_user.email if other_user else 'Unknown',
            'partner_role': other_user.role if other_user else 'Unknown',
            'tuteeName': session_detail.get('student_name'),
            'tutor_name': session_detail.get('tutor_name'),
            'university': session_detail.get('university'),
            'year': session_detail.get('year'),
            'subject': session_detail.get('subject'),
            'date': session_detail.get('date'),
            'time': session_detail.get('time'),
            'format': session_detail.get('format'),
            'message': session_detail.get('message'),
            'gradient': session_detail.get('gradient'),
            'rejectReason': session_detail.get('rejectReason'),
        })

    return jsonify(results), 200


@sessions_bp.route('/create', methods=['OPTIONS', 'POST'])
def create_session():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json or {}
    tutor_id = data.get('tutor_id')
    if not tutor_id:
        return jsonify({"message": "Tutor is required"}), 400

    tutor = User.query.get(tutor_id)
    student = User.query.get(user_id)
    if not tutor or tutor.role != 'tutor':
        return jsonify({"message": "Tutor not found"}), 404

    new_session = Session(tutee_id=user_id, tutor_id=tutor_id, status='pending')
    db.session.add(new_session)
    db.session.commit()

    details = load_session_details()
    details[str(new_session.id)] = {
        'student_name': student.full_name if student else 'Student',
        'tutor_name': tutor.full_name,
        'university': data.get('university') or 'University',
        'year': data.get('year') or 'N/A',
        'subject': data.get('subject') or 'General Session',
        'date': data.get('date') or 'TBD',
        'time': data.get('time') or 'TBD',
        'format': data.get('format') or 'online',
        'message': data.get('message') or 'No message provided.',
        'gradient': data.get('gradient') or 'from-cyan-500 to-blue-600',
        'rejectReason': '',
    }
    save_session_details(details)

    return jsonify({
        "message": "Session request sent successfully",
        "session_id": new_session.id,
    }), 201


@sessions_bp.route('/<int:id>/<action>', methods=['OPTIONS', 'POST'])
def update_session(id, action):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user_id = get_current_user_from_request()
    session = Session.query.get(id)
    if not session or session.tutor_id != user_id:
        return jsonify({"message": "Not found"}), 404

    details = load_session_details()
    session_detail = details.get(str(id), {})

    if action == 'accept':
        session.status = 'accepted'
    elif action == 'reject':
        session.status = 'declined'
        reject_reason = (request.json or {}).get('reason', '').strip()
        session_detail['rejectReason'] = reject_reason
        details[str(id)] = session_detail
        save_session_details(details)
    elif action == 'complete':
        session.status = 'completed'
    else:
        return jsonify({"message": "Invalid action"}), 400

    db.session.commit()
    return jsonify({"message": f"Session {action}ed"}), 200
