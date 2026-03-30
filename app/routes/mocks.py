from flask import Blueprint, jsonify, request
from ..models import Feedback, Message, Session, User
import jwt
import json
from pathlib import Path

finance_bp = Blueprint("finance", __name__)
progress_bp = Blueprint("progress", __name__)
notifications_bp = Blueprint("notifications", __name__)

JWT_SECRET = "supersecretkey"
NOTIFICATION_STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "notification_state.json"
QUIZ_RESULTS_FILE = Path(__file__).resolve().parents[1] / "data" / "progress_quiz_results.json"

SUBJECT_QUIZZES = {
    "Calculus II": {
        "id": "calc-2-basics",
        "title": "Calculus II Check-in",
        "questions": [
            {
                "id": "calc-q1",
                "prompt": "How confident are you with integration techniques?",
                "options": ["Not confident", "Somewhat confident", "Very confident"],
            },
            {
                "id": "calc-q2",
                "prompt": "Which topic feels hardest right now?",
                "options": ["Trig integrals", "Series", "Applications"],
            },
        ],
    },
    "Data Structures": {
        "id": "ds-core",
        "title": "Data Structures Check-in",
        "questions": [
            {
                "id": "ds-q1",
                "prompt": "Which structure do you understand best?",
                "options": ["Arrays", "Linked lists", "Trees"],
            },
            {
                "id": "ds-q2",
                "prompt": "How comfortable are you with recursion?",
                "options": ["Not yet", "Getting there", "Comfortable"],
            },
        ],
    },
}


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


def load_json_file(path):
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_file(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_notification_state():
    return load_json_file(NOTIFICATION_STATE_FILE)


def get_quiz_results():
    return load_json_file(QUIZ_RESULTS_FILE)


def build_notifications_for_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return []

    items = []

    if user.role == "tutor":
        sessions = Session.query.filter_by(tutor_id=user_id).order_by(Session.created_at.desc()).limit(10).all()
        for session in sessions:
            student = User.query.get(session.tutee_id)
            if not student:
                continue
            items.append({
                "id": f"session-{session.id}",
                "message": f"{student.full_name} {('requested a session' if session.status == 'pending' else f'session is {session.status}')}",
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "type": "session",
            })
    else:
        sessions = Session.query.filter_by(tutee_id=user_id).order_by(Session.created_at.desc()).limit(10).all()
        for session in sessions:
            tutor = User.query.get(session.tutor_id)
            if not tutor:
                continue
            items.append({
                "id": f"session-{session.id}",
                "message": f"{tutor.full_name} {('received your session request' if session.status == 'pending' else f'session is {session.status}')}",
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "type": "session",
            })

    messages = Message.query.filter_by(receiver_id=user_id).order_by(Message.timestamp.desc()).limit(10).all()
    for msg in messages:
        sender = User.query.get(msg.sender_id)
        if not sender:
            continue
        preview = (msg.content or "sent you a message").strip()
        if len(preview) > 40:
            preview = f"{preview[:37]}..."
        items.append({
            "id": f"message-{msg.id}",
            "message": f"{sender.full_name}: {preview}",
            "created_at": msg.timestamp.isoformat() if msg.timestamp else None,
            "type": "message",
        })

    state = get_notification_state()
    read_ids = set(state.get(str(user_id), {}).get("read_ids", []))

    for item in items:
        item["is_read"] = item["id"] in read_ids

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return items[:20]


@finance_bp.route("/wallet", methods=["GET"])
def get_wallet():
    return jsonify({"balance": 0}), 200


@progress_bp.route("/", methods=["GET"])
def get_progress():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    sessions = Session.query.filter_by(tutee_id=user_id).order_by(Session.created_at.desc()).all()
    completed_sessions = [session for session in sessions if session.status == "accepted"]
    received_feedback = Feedback.query.filter_by(from_user_id=user_id).all()
    quiz_results = get_quiz_results().get(str(user_id), {})

    subject_counts = {}
    for session in sessions:
        partner = User.query.get(session.tutor_id)
        subject = "General Session"
        subject_counts.setdefault(subject, {"sessions": 0})
        subject_counts[subject]["sessions"] += 1

    if not subject_counts:
        subjects = ["General Study", "Goal Tracking", "Confidence"]
        subjectProgress = [
            {"subject": subject, "confidence": 0, "trend": "+0%", "trendUp": True, "sessions": 0}
            for subject in subjects
        ]
    else:
        subjectProgress = []
        for index, (subject, info) in enumerate(subject_counts.items()):
            confidence = min(95, 45 + info["sessions"] * 8 + index * 3)
            subjectProgress.append({
                "subject": subject,
                "confidence": confidence,
                "trend": f"+{min(25, info['sessions'] * 3)}%",
                "trendUp": True,
                "sessions": info["sessions"],
            })

    sessionHistory = []
    for session in sessions[:8]:
        tutor = User.query.get(session.tutor_id)
        sessionHistory.append({
            "id": session.id,
            "tutor": tutor.full_name if tutor else "Unknown Tutor",
            "subject": "General Session",
            "date": session.created_at.strftime("%d %b %Y") if session.created_at else "N/A",
            "rating": 5 if session.status == "accepted" else 0,
        })

    avg_rating = 0
    if received_feedback:
        avg_rating = round(sum(item.rating for item in received_feedback) / len(received_feedback), 1)

    statCards = [
        {
            "icon": "trending_up",
            "label": "GPA Boost",
            "value": f"+{min(18, len(completed_sessions) * 2)}%",
            "sub": "Average improvement",
            "color": "bg-green-50 text-green-600",
        },
        {
            "icon": "event_available",
            "label": "Sessions",
            "value": str(len(completed_sessions)),
            "sub": "Completed this semester",
            "color": "bg-blue-50 text-primary",
        },
        {
            "icon": "schedule",
            "label": "Hours",
            "value": str(len(completed_sessions)),
            "sub": "Total study time",
            "color": "bg-purple-50 text-purple-600",
        },
        {
            "icon": "star",
            "label": "Avg Rating",
            "value": str(avg_rating),
            "sub": "Your tutor ratings",
            "color": "bg-yellow-50 text-yellow-600",
        },
    ]

    return jsonify({
        "subjectProgress": subjectProgress,
        "sessionHistory": sessionHistory,
        "statCards": statCards,
        "quizResults": quiz_results,
    }), 200


@progress_bp.route("/quiz", methods=["GET"])
def get_quiz():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    subject = request.args.get("subject", "").strip()
    quiz = SUBJECT_QUIZZES.get(subject) or {
        "id": "general-study-check",
        "title": f"{subject or 'Study'} Check-in",
        "questions": [
            {
                "id": "general-q1",
                "prompt": "How confident do you feel in this subject?",
                "options": ["Need help", "Improving", "Strong"],
            }
        ],
    }
    return jsonify(quiz), 200


@progress_bp.route("/quiz/submit", methods=["POST"])
def submit_quiz():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json() or {}
    quiz_id = data.get("quizId") or "unknown-quiz"
    answers = data.get("answers") or {}
    stored = get_quiz_results()
    user_results = stored.get(str(user_id), {})
    user_results[quiz_id] = {
        "answers": answers,
        "score": len([value for value in answers.values() if value not in (None, "")]),
    }
    stored[str(user_id)] = user_results
    save_json_file(QUIZ_RESULTS_FILE, stored)
    return jsonify({"message": "Quiz submitted", "score": user_results[quiz_id]["score"]}), 200


@notifications_bp.route("/", methods=["GET", "OPTIONS"])
def get_all_notifications():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    return jsonify(build_notifications_for_user(user_id)), 200


@notifications_bp.route("/unread", methods=["GET"])
def get_unread():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    unread = [item for item in build_notifications_for_user(user_id) if not item.get("is_read")]
    return jsonify(unread), 200


@notifications_bp.route("/<notification_id>/read", methods=["POST"])
def mark_as_read(notification_id):
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    state = get_notification_state()
    user_state = state.get(str(user_id), {"read_ids": []})
    read_ids = set(user_state.get("read_ids", []))
    read_ids.add(notification_id)
    user_state["read_ids"] = sorted(read_ids)
    state[str(user_id)] = user_state
    save_json_file(NOTIFICATION_STATE_FILE, state)
    return jsonify({"message": "Notification marked as read"}), 200


@notifications_bp.route("/read-all", methods=["POST"])
def mark_all_as_read():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    items = build_notifications_for_user(user_id)
    state = get_notification_state()
    state[str(user_id)] = {"read_ids": [item["id"] for item in items]}
    save_json_file(NOTIFICATION_STATE_FILE, state)
    return jsonify({"message": "All notifications marked as read"}), 200
