from flask import Blueprint, request, jsonify
from app.database import db
from app.models import TutorProfile, User
import jwt
import json
from pathlib import Path

tutors_bp = Blueprint('tutors', __name__)
JWT_SECRET = "supersecretkey"
EXTRAS_FILE = Path(__file__).resolve().parents[1] / "data" / "tutor_profile_extras.json"


def load_tutor_extras():
    if not EXTRAS_FILE.exists():
        return {}

    try:
        return json.loads(EXTRAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_tutor_extras(extras):
    EXTRAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXTRAS_FILE.write_text(json.dumps(extras, indent=2), encoding="utf-8")

def get_current_user_from_request():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None

    parts = auth_header.split(" ")
    if len(parts) != 2:
        return None

    try:
        data = jwt.decode(parts[1], JWT_SECRET, algorithms=["HS256"])
        return data.get('user_id')
    except Exception:
        return None

@tutors_bp.route('/', methods=['GET'])
def list_tutors():
    subject = request.args.get('subject')
    query = User.query.filter_by(role='tutor')
    if subject:
        query = query.join(TutorProfile).filter(TutorProfile.subjects.ilike(f'%{subject}%'))

    extras = load_tutor_extras()
    tutors = query.all()
    results = []
    for t in tutors:
        profile = getattr(t, 'tutor_profile', None)
        profile_extras = extras.get(str(t.id), {})
        subjects_list = []
        if profile and profile.subjects:
            subjects_list = [s.strip() for s in profile.subjects.split(',')]

        results.append({
            'id': t.id,
            'name': t.full_name,
            'email': t.email,
            'subjects': subjects_list,
            'availability': getattr(profile, 'availability', 'Flexible') if profile else 'Flexible',
            'rating': 4.5,
            'experience_level': getattr(profile, 'experience_level', 'Intermediate') if profile else 'Intermediate',
            'bio': profile_extras.get('bio') or 'Hi, I am ready to tutor!',
            'university': profile_extras.get('university') or 'University not provided',
            'teaching_approach': profile_extras.get('teaching_approach') or '',
            'profile_photo': profile_extras.get('profile_photo') or '',
        })
    return jsonify(results), 200

@tutors_bp.route('/create', methods=['OPTIONS', 'POST'])
def create_profile():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    
    def _create_profile():
        user_id = get_current_user_from_request()
        if not user_id:
            return jsonify({"message": "Unauthorized"}), 401

        data = request.json
        profile = TutorProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = TutorProfile(user_id=user_id)
            db.session.add(profile)
        
        subjects = data.get('subjects', [])
        if isinstance(subjects, list):
            profile.subjects = ', '.join(subjects)
        else:
            profile.subjects = subjects
            
        profile.availability = data.get('availability', 'Flexible')
        
        # update user role to tutor
        user = User.query.get(user_id)
        if user and user.role != 'tutor':
            user.role = 'tutor'
            
        db.session.commit()
        return jsonify({"message": "Profile created successfully"}), 201

    return _create_profile()


@tutors_bp.route('/update', methods=['OPTIONS', 'PUT'])
def update_profile():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user_id = get_current_user_from_request()
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json or {}
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    profile = TutorProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = TutorProfile(user_id=user_id, subjects="", availability="Flexible")
        db.session.add(profile)

    full_name = (data.get('full_name') or "").strip()
    if full_name:
        user.full_name = full_name

    subjects = data.get('subjects', [])
    if isinstance(subjects, list):
        profile.subjects = ', '.join([s.strip() for s in subjects if isinstance(s, str) and s.strip()])
    elif isinstance(subjects, str):
        profile.subjects = subjects

    if 'availability' in data and data.get('availability'):
        profile.availability = data.get('availability')

    extras = load_tutor_extras()
    existing_extras = extras.get(str(user_id), {})
    extras[str(user_id)] = {
        **existing_extras,
        "bio": (data.get("bio") or existing_extras.get("bio") or "").strip(),
        "university": (data.get("university") or existing_extras.get("university") or "").strip(),
        "teaching_approach": (data.get("teaching_approach") or existing_extras.get("teaching_approach") or "").strip(),
        "profile_photo": data.get("profile_photo") or existing_extras.get("profile_photo") or "",
    }
    save_tutor_extras(extras)

    db.session.commit()

    return jsonify({
        "message": "Tutor profile updated successfully",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "subjects": [s.strip() for s in (profile.subjects or "").split(',') if s.strip()],
            "availability": profile.availability or "Flexible",
            "bio": extras[str(user_id)].get("bio", ""),
            "university": extras[str(user_id)].get("university", ""),
            "teaching_approach": extras[str(user_id)].get("teaching_approach", ""),
            "profile_photo": extras[str(user_id)].get("profile_photo", ""),
        }
    }), 200
