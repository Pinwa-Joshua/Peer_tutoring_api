from flask import Blueprint, request, jsonify
from ..models import Message
from ..database import db
import jwt
import json
from pathlib import Path

messages_bp = Blueprint("messages", __name__)
JWT_SECRET = "supersecretkey"
ATTACHMENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "message_attachments.json"


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


def load_attachments():
    if not ATTACHMENTS_FILE.exists():
        return {}

    try:
        return json.loads(ATTACHMENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_attachments(attachments):
    ATTACHMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_FILE.write_text(json.dumps(attachments, indent=2), encoding="utf-8")


@messages_bp.route("/send", methods=["POST"])
def send_message():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json() or {}
    receiver_id = data.get("receiver_id")
    content = (data.get("content") or "").strip()
    attachment = data.get("attachment")

    if not receiver_id:
        return jsonify({"message": "Receiver is required"}), 400

    if not content and not attachment:
        return jsonify({"message": "Message content or attachment is required"}), 400

    msg = Message(
        sender_id=user_id,
        receiver_id=receiver_id,
        content=content or (attachment.get("name") if isinstance(attachment, dict) else "Attachment"),
    )
    db.session.add(msg)
    db.session.commit()

    if attachment and isinstance(attachment, dict):
        attachments = load_attachments()
        attachments[str(msg.id)] = {
            "name": attachment.get("name") or "attachment",
            "type": attachment.get("type") or "application/octet-stream",
            "data_url": attachment.get("data_url") or "",
            "size": attachment.get("size") or 0,
        }
        save_attachments(attachments)

    return jsonify({"message": "Message sent", "id": msg.id})


@messages_bp.route("/inbox", methods=["GET"])
def inbox():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    msgs = Message.query.filter_by(receiver_id=user_id).all()
    sent_msgs = Message.query.filter_by(sender_id=user_id).all()
    all_msgs = msgs + sent_msgs
    attachments = load_attachments()

    result = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "receiver_id": m.receiver_id,
        "content": m.content,
        "timestamp": m.timestamp,
        "attachment": attachments.get(str(m.id)),
        "sender": {
            "id": m.sender.id,
            "name": m.sender.full_name if hasattr(m.sender, 'full_name') else f"User {m.sender.id}"
        } if m.sender else None,
        "receiver": {
            "id": m.receiver.id,
            "name": m.receiver.full_name if hasattr(m.receiver, 'full_name') else f"User {m.receiver.id}"
        } if m.receiver else None
    } for m in all_msgs]
    return jsonify(result)


@messages_bp.route("/thread/<int:other_id>", methods=["GET"])
def thread(other_id):
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    msgs = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == user_id))
    ).order_by(Message.timestamp).all()
    attachments = load_attachments()

    result = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "receiver_id": m.receiver_id,
        "content": m.content,
        "timestamp": m.timestamp,
        "attachment": attachments.get(str(m.id)),
    } for m in msgs]
    return jsonify(result)


@messages_bp.route("/<int:message_id>", methods=["DELETE"])
def delete_message(message_id):
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    msg = Message.query.get(message_id)
    if not msg:
        return jsonify({"message": "Message not found"}), 404

    if msg.sender_id != user_id:
        return jsonify({"message": "You can only delete your own messages"}), 403

    attachments = load_attachments()
    if str(message_id) in attachments:
        attachments.pop(str(message_id), None)
        save_attachments(attachments)

    db.session.delete(msg)
    db.session.commit()
    return jsonify({"message": "Message deleted"})


@messages_bp.route("/delete-many", methods=["POST"])
def delete_many_messages():
    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json() or {}
    message_ids = data.get("message_ids") or []
    if not isinstance(message_ids, list) or not message_ids:
        return jsonify({"message": "message_ids is required"}), 400

    normalized_ids = []
    for message_id in message_ids:
        try:
            normalized_ids.append(int(message_id))
        except (TypeError, ValueError):
            continue

    if not normalized_ids:
        return jsonify({"message": "No valid message ids provided"}), 400

    messages = Message.query.filter(Message.id.in_(normalized_ids)).all()
    owned_messages = [msg for msg in messages if msg.sender_id == user_id]

    if not owned_messages:
        return jsonify({"message": "No deletable messages found"}), 404

    attachments = load_attachments()
    for msg in owned_messages:
        attachments.pop(str(msg.id), None)
        db.session.delete(msg)

    save_attachments(attachments)
    db.session.commit()

    return jsonify({
        "message": "Messages deleted",
        "deleted_ids": [msg.id for msg in owned_messages],
    })
