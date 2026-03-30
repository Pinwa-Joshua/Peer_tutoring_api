from flask import Blueprint, request, jsonify
from ..models import Feedback
from ..database import db
from flask_jwt_extended import jwt_required, get_jwt_identity

feedback_bp = Blueprint("feedback", __name__)

# Submit feedback
@feedback_bp.route("/submit", methods=["OPTIONS", "POST"])
def submit_feedback():
    if request.method == "OPTIONS":
        return jsonify({}), 200
        
    @jwt_required()
    def _submit():
        data = request.get_json()
        feedback = Feedback(
            from_user_id=get_jwt_identity(),
            to_user_id=data.get("to_user_id"),
            session_id=data.get("session_id"),
            rating=data["rating"],
            comment=data.get("comment") or data.get("comments")
        )
        db.session.add(feedback)
        db.session.commit()
        return jsonify({"message": "Feedback submitted"})
        
    return _submit()
