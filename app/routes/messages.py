from flask import Blueprint, request, jsonify
from ..models import Message
from ..database import db
from flask_jwt_extended import jwt_required, get_jwt_identity

messages_bp = Blueprint("messages", __name__)

# Send message
@messages_bp.route("/send", methods=["POST"])
@jwt_required()
def send_message():
    data = request.get_json()
    msg = Message(
        sender_id=get_jwt_identity(),
        receiver_id=data["receiver_id"],
        content=data["content"]
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": "Message sent"})

# Get my messages
@messages_bp.route("/inbox", methods=["GET"])
@jwt_required()
def inbox():
    user_id = get_jwt_identity()
    msgs = Message.query.filter_by(receiver_id=user_id).all()
    result = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "content": m.content,
        "timestamp": m.timestamp
    } for m in msgs]
    return jsonify(result)
