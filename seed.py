
import sys
sys.path.append(r'c:/Users/MVP/Downloads/PeerPal/BACKEND/Peer_tutoring_api')
from app import create_app
from app.database import db
from app.models import User, TutorProfile, Session, Feedback

app = create_app()
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='student@example.com').first():
        student = User(full_name='Alice Student', email='student@example.com', role='tutee')
        student.set_password('password')
        db.session.add(student)
        
        tutor = User(full_name='Bob Tutor', email='tutor@example.com', role='tutor')
        tutor.set_password('password')
        db.session.add(tutor)
        db.session.commit()

        tp1 = TutorProfile(user_id=tutor.id, subjects='Computer Science, UI/UX', availability='Mon-Fri')
        db.session.add(tp1)
        db.session.commit()

        sess = Session(tutor_id=tutor.id, tutee_id=student.id, status='pending')
        db.session.add(sess)
        db.session.commit()
        print('DB Seeded')
    else:
        print('DB already seeded')
