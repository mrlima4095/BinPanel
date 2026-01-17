import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-super-secreta-aqui'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///server_panel.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'sua-chave-jwt-secreta'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 2525
    MAIL_USE_TLS = False
    SMTP_PORT = 25
    POSTMAIL_PORT = 2525