from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import db
from ..models import TutorProfile, User

tutors_bp = Blueprint("tutors", __name__)

@tutors_bp.route("/")
def tutors_home():
    return {"message": "Tutors route working"}

@tutors_bp.route("/profile", methods=["POST"])
@jwt_required()
def create_profile():
    user_id = get_jwt_identity()
    data = request.json

    profile = TutorProfile(
        user_id=user_id,
        subjects=data["subjects"],
        experience_level=data["experience_level"]
    )
    db.session.add(profile)
    db.session.commit()

    return jsonify({"message": "Tutor profile created"}), 201


@tutors_bp.route("/tutors", methods=["GET"])
def list_tutors():
    subject = request.args.get("subject")

    query = TutorProfile.query
    if subject:
        query = query.filter(TutorProfile.subjects.ilike(f"%{subject}%"))

    tutors = query.all()

    return jsonify([
        {
            "tutor_id": t.user_id,
            "subjects": t.subjects,
            "experience_level": t.experience_level,
            "rating": t.average_rating
        } for t in tutors
    ])
