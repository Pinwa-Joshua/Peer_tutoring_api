from flask import Blueprint, request, jsonify
from ..models import Session, User
from ..database import db
from flask_jwt_extended import jwt_required, get_jwt_identity

matches_bp = Blueprint("matches", __name__)

# Create a new match/session
@matches_bp.route("/create", methods=["POST"])
@jwt_required()
def create_match():
    data = request.get_json()
    tutor_id = data["tutor_id"]
    tutee_id = get_jwt_identity()
    session = Session(tutor_id=tutor_id, tutee_id=tutee_id)
    db.session.add(session)
    db.session.commit()
    return jsonify({"message": "Session created", "session_id": session.id})

# List my sessions
@matches_bp.route("/my-sessions", methods=["GET"])
@jwt_required()
def my_sessions():
    user_id = get_jwt_identity()
    sessions = Session.query.filter(
        (Session.tutor_id==user_id) | (Session.tutee_id==user_id)
    ).all()
    result = [{
        "id": s.id,
        "tutor_id": s.tutor_id,
        "tutee_id": s.tutee_id,
        "status": s.status
    } for s in sessions]
    return jsonify(result)

@matches_bp.route("/recommend", methods=["POST"])
def recommend_tutor():
    from ..models import TutorProfile, User
    data = request.get_json() or {}
    subject_query = (data.get("subject") or "").strip().lower()

    tutors = TutorProfile.query.join(User).all()
    candidates = []

    for tutor_profile in tutors:
        subject_list = [item.strip() for item in (tutor_profile.subjects or "").split(",") if item.strip()]
        matches_subject = (
            not subject_query
            or any(subject_query in subject.lower() for subject in subject_list)
            or subject_query in tutor_profile.user.full_name.lower()
        )
        score = len(subject_list) + (20 if matches_subject else 0)

        candidates.append({
            "id": tutor_profile.user_id,
            "name": tutor_profile.user.full_name,
            "email": tutor_profile.user.email,
            "subjects": subject_list,
            "availability": getattr(tutor_profile, "availability", "Flexible"),
            "rating": 4.5,
            "experience_level": getattr(tutor_profile, "experience_level", "Intermediate"),
            "score": score,
        })

    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    matched = [item for item in ranked if not subject_query or item["score"] >= 20]

    if not matched and ranked:
        best = ranked[0]
    elif matched:
        best = matched[0]
    else:
        return jsonify({"message": "No tutors available right now."}), 200

    return jsonify({
        "message": "Top tutor recommendation generated successfully.",
        "tutor": {
            "id": best["id"],
            "name": best["name"],
            "email": best["email"],
            "subjects": best["subjects"],
            "availability": best["availability"],
            "rating": best["rating"],
            "experience_level": best["experience_level"],
        },
        "candidates": [
            {
                "id": item["id"],
                "name": item["name"],
                "email": item["email"],
                "subjects": item["subjects"],
                "availability": item["availability"],
                "rating": item["rating"],
                "experience_level": item["experience_level"],
            }
            for item in ranked[:5]
        ],
    }), 200
