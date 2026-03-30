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
