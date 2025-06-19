import os
from flask import Flask
from flask_session import Session
from config import SECRET_KEY, USE_LOCAL_DB
from models import db
from routes.auth import auth_bp
from routes.post import post_bp
from routes.comment import comment_bp
from flask_mail import Mail, Message
import config
from mail import mail

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'

if USE_LOCAL_DB:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
Session(app)

# 블루프린트 등록
app.register_blueprint(auth_bp)
app.register_blueprint(post_bp)
app.register_blueprint(comment_bp)

mail.init_app(app)

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    mail.init_app(app)
    return app

if __name__ == '__main__':
    app.run(debug=True, port=5001)
