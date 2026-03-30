from flask import Flask
from .config import Config
from .database import db, migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

jwt = JWTManager()

def create_app():
    app= Flask(__name__)
    CORS(app) # Enable CORS for all routes so the React frontend can communicate with it
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)  

    from .routes.users import users_bp
    from .routes.tutors import tutors_bp
    from .routes.matches import matches_bp
    from .routes.feedback import feedback_bp
    from .routes.messages import messages_bp

    app.register_blueprint(matches_bp, url_prefix="/api/matches")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
    app.register_blueprint(users_bp,url_prefix="/api/users")
    app.register_blueprint(tutors_bp, url_prefix="/api/tutors")


    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return RevokedToken.query.filter_by(jti=jti).first() is not None

    @app.route('/')
    def home():
        return "Online!", 200

    return app
