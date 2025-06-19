from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import bcrypt
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        nickname = request.form['nickname']
        password = request.form['password']
        if User.query.filter((User.email == email) | (User.nickname == nickname)).first():
            flash('이미 사용 중인 이메일 또는 닉네임입니다.')
            return render_template('register.html')
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        email_notify = bool(request.form.get('email_notify'))
        user = User(email=email, nickname=nickname, password_hash=hashed.decode('utf-8'), is_admin=False, email_notify=email_notify)
        db.session.add(user)
        db.session.commit()
        flash('회원가입 완료! 로그인 해주세요.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            session['user_id'] = user.id
            session['nickname'] = user.nickname
            session['is_admin'] = user.is_admin
            flash('로그인 성공!')
            return redirect(url_for('post.index'))
        flash('이메일 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('로그아웃 되었습니다.')
    return redirect(url_for('post.index'))

@auth_bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        nickname = request.form.get('nickname', user.nickname)
        email_notify = bool(request.form.get('email_notify'))
        password = request.form.get('password')
        user.nickname = nickname
        user.email_notify = email_notify
        if password:
            user.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.session.commit()
        session['nickname'] = user.nickname
        flash('정보가 수정되었습니다.')
        return redirect(url_for('auth.mypage'))
    return render_template('mypage.html', user=user) 