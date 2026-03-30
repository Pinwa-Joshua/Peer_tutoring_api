import os

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:pinwaj2006@localhost:5432/peer_tutoring_new"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")

