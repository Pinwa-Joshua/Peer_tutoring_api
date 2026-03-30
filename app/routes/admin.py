from flask import Blueprint, jsonify, request
from ..models import Feedback, Message, Session, User
from ..routes.sessions import load_session_details
import jwt

admin_bp = Blueprint("admin", __name__)
JWT_SECRET = "supersecretkey"


def get_current_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split(" ")
    if len(parts) != 2:
        return None

    try:
        payload = jwt.decode(parts[1], JWT_SECRET, algorithms=["HS256"])
        user = User.query.get(payload.get("user_id"))
        if not user or user.role != "admin":
            return None
        return user
    except Exception:
        return None


def require_admin():
    admin_user = get_current_user()
    if not admin_user:
        return None, (jsonify({"message": "Unauthorized"}), 401)
    return admin_user, None


@admin_bp.route("/overview", methods=["GET"])
def overview():
    _, error = require_admin()
    if error:
        return error

    users = User.query.all()
    sessions = Session.query.all()
    feedback_entries = Feedback.query.all()
    messages = Message.query.all()

    total_users = len(users)
    total_tutors = len([user for user in users if user.role == "tutor"])
    total_students = len([user for user in users if user.role != "tutor" and user.role != "admin"])
    active_sessions = len([session for session in sessions if session.status in ("pending", "accepted")])
    completed_sessions = len([session for session in sessions if session.status == "accepted"])
    flagged_feedback = len([entry for entry in feedback_entries if (entry.rating or 0) <= 2])

    recent_activity = []
    for session in sorted(sessions, key=lambda item: item.created_at or 0, reverse=True)[:5]:
        tutor = User.query.get(session.tutor_id)
        student = User.query.get(session.tutee_id)
        recent_activity.append({
            "id": f"session-{session.id}",
            "user": student.full_name if student else "Unknown Student",
            "action": f"Session with {tutor.full_name if tutor else 'Unknown Tutor'}",
            "time": session.created_at.isoformat() if session.created_at else "",
            "status": session.status,
        })

    for message in sorted(messages, key=lambda item: item.timestamp or 0, reverse=True)[:5]:
        sender = User.query.get(message.sender_id)
        recent_activity.append({
            "id": f"message-{message.id}",
            "user": sender.full_name if sender else "Unknown User",
            "action": "Sent a message",
            "time": message.timestamp.isoformat() if message.timestamp else "",
            "status": "message",
        })

    recent_activity.sort(key=lambda item: item.get("time") or "", reverse=True)

    return jsonify({
        "stats": {
            "total_users": total_users,
            "active_tutors": total_tutors,
            "students": total_students,
            "active_sessions": active_sessions,
            "completed_sessions": completed_sessions,
            "flagged_feedback": flagged_feedback,
        },
        "recent_activity": recent_activity[:6],
    }), 200


@admin_bp.route("/users", methods=["GET"])
def list_users():
    _, error = require_admin()
    if error:
        return error

    role = (request.args.get("role") or "").strip()
    query = (request.args.get("q") or "").strip().lower()

    users = User.query.order_by(User.id.desc()).all()
    session_details = load_session_details()
    user_rows = []

    for user in users:
        if role and user.role != role:
            continue
        if query and query not in f"{user.full_name} {user.email} {user.role}".lower():
            continue

        related_sessions = [session for session in Session.query.all() if session.tutor_id == user.id or session.tutee_id == user.id]
        latest_session = sorted(related_sessions, key=lambda item: item.created_at or 0, reverse=True)[0] if related_sessions else None

        user_rows.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "sessions_count": len(related_sessions),
            "latest_session_id": latest_session.id if latest_session else None,
            "latest_session_subject": session_details.get(str(latest_session.id), {}).get("subject") if latest_session else "",
            "joined_at": latest_session.created_at.isoformat() if latest_session and latest_session.created_at else "",
        })

    return jsonify(user_rows), 200


@admin_bp.route("/sessions", methods=["GET"])
def list_sessions():
    _, error = require_admin()
    if error:
        return error

    status_filter = (request.args.get("status") or "").strip()
    details = load_session_details()
    sessions = Session.query.order_by(Session.created_at.desc()).all()

    rows = []
    for session in sessions:
        if status_filter and session.status != status_filter:
            continue

        tutor = User.query.get(session.tutor_id)
        student = User.query.get(session.tutee_id)
        detail = details.get(str(session.id), {})

        rows.append({
            "id": session.id,
            "status": session.status,
            "student": student.full_name if student else "Unknown Student",
            "tutor": tutor.full_name if tutor else "Unknown Tutor",
            "subject": detail.get("subject") or "General Session",
            "date": detail.get("date") or "",
            "time": detail.get("time") or "",
            "format": detail.get("format") or "",
            "created_at": session.created_at.isoformat() if session.created_at else "",
        })

    return jsonify(rows), 200


@admin_bp.route("/feedback", methods=["GET"])
def list_feedback():
    _, error = require_admin()
    if error:
        return error

    rows = []
    for entry in Feedback.query.order_by(Feedback.created_at.desc()).all():
        from_user = User.query.get(entry.from_user_id)
        to_user = User.query.get(entry.to_user_id)
        rows.append({
            "id": entry.id,
            "from_user": from_user.full_name if from_user else "Unknown User",
            "from_role": from_user.role if from_user else "unknown",
            "to_user": to_user.full_name if to_user else "Unknown User",
            "rating": entry.rating,
            "comment": entry.comment or "",
            "session_id": entry.session_id,
            "created_at": entry.created_at.isoformat() if entry.created_at else "",
            "flagged": (entry.rating or 0) <= 2,
        })

    return jsonify(rows), 200


@admin_bp.route("/payouts", methods=["GET"])
def payouts():
    _, error = require_admin()
    if error:
        return error

    tutors = [user for user in User.query.all() if user.role == "tutor"]
    details = load_session_details()
    payout_rows = []

    for tutor in tutors:
        tutor_sessions = [session for session in Session.query.all() if session.tutor_id == tutor.id and session.status == "accepted"]
        estimated_earnings = 0
        subjects = set()
        for session in tutor_sessions:
            detail = details.get(str(session.id), {})
            subjects.add(detail.get("subject") or "General Session")
            estimated_earnings += 100

        payout_rows.append({
            "id": tutor.id,
            "tutor": tutor.full_name,
            "email": tutor.email,
            "sessions_completed": len(tutor_sessions),
            "subjects": sorted(subjects),
            "estimated_earnings": estimated_earnings,
        })

    payout_rows.sort(key=lambda item: item["estimated_earnings"], reverse=True)
    return jsonify(payout_rows), 200
