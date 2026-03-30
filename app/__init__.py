from flask import Flask
from .config import Config
from .database import db, migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

jwt = JWTManager()

def create_app():
    app= Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)  

    from .routes.users import users_bp
    from .routes.tutors import tutors_bp
    from .routes.matches import matches_bp
    from .routes.feedback import feedback_bp
    from .routes.messages import messages_bp
    from .routes.auth import auth_bp
    from .routes.sessions import sessions_bp
    from .routes.mocks import finance_bp, progress_bp, notifications_bp
    from .routes.admin import admin_bp
    app.register_blueprint(finance_bp, url_prefix='/api/finance')
    app.register_blueprint(progress_bp, url_prefix='/api/progress')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    app.register_blueprint(matches_bp, url_prefix="/api/matches")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
    app.register_blueprint(users_bp,url_prefix="/api/users")
    app.register_blueprint(tutors_bp, url_prefix="/api/tutors")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(sessions_bp, url_prefix="/api/sessions")


    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return RevokedToken.query.filter_by(jti=jti).first() is not None

    @app.route('/')
    def home():
        return "Online!", 200

    return app
