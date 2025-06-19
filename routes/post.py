from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from models import db, Post, User, Comment
import os
from functools import wraps
from mail import send_email

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

post_bp = Blueprint('post', __name__)

@post_bp.route('/')
def index():
    posts = Post.query.order_by(Post.id.desc()).all()
    for post in posts:
        post.image_urls = post.image_filenames.split(',') if post.image_filenames else []
        post.author = User.query.get(post.user_id)
    return render_template('index.html', posts=posts)

@post_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        files = request.files.getlist('images')
        filenames = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join('uploads', filename))
                filenames.append(filename)
        post = Post(user_id=session['user_id'], title=title, description=description, image_filenames=','.join(filenames))
        db.session.add(post)
        db.session.commit()
        flash('글이 등록되었습니다!')
        # 이메일 알림
        notify_users = User.query.filter(User.email_notify==True, User.id!=session['user_id']).all()
        if notify_users:
            emails = [u.email for u in notify_users]
            post_url = url_for('post.post_detail', post_id=post.id, _external=True)
            subject = f"[glasses] 새 글: {title}"
            body = f"{session.get('nickname','')}님이 새 글을 작성했습니다.\n\n제목: {title}\n\n{description}\n\n바로가기: {post_url}"
            send_email(subject, emails, body)
        return redirect(url_for('post.index'))
    return render_template('create_post.html')

@post_bp.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = Post.query.get(post_id)
    if not post:
        flash('글을 찾을 수 없습니다.')
        return redirect(url_for('post.index'))
    post.image_urls = post.image_filenames.split(',') if post.image_filenames else []
    author = User.query.get(post.user_id)
    comments = Comment.query.filter_by(post_id=post_id).all()
    nick_map = {u.id: u.nickname for u in User.query.filter(User.id.in_([c.user_id for c in comments])).all()}
    # 댓글 작성
    if request.method == 'POST' and 'user_id' in session:
        text = request.form.get('text', '').strip()
        if text:
            comment = Comment(post_id=post_id, user_id=session['user_id'], text=text)
            db.session.add(comment)
            db.session.commit()
            flash('댓글이 등록되었습니다!')
            # 이메일 알림 (글쓴이+구독자, 단 본인 제외)
            exclude_ids = [session['user_id'], post.user_id]
            notify_users = User.query.filter(User.email_notify==True, ~User.id.in_(exclude_ids)).all()
            emails = [u.email for u in notify_users]
            # 글쓴이에게도 알림(본인 댓글이 아니면)
            if post.user_id != session['user_id']:
                author = User.query.get(post.user_id)
                if author and author.email_notify:
                    emails.append(author.email)
            if emails:
                post_url = url_for('post.post_detail', post_id=post.id, _external=True)
                subject = f"[glasses] 새 댓글: {post.title}"
                body = f"{session.get('nickname','')}님이 댓글을 남겼습니다.\n\n댓글: {text}\n\n글 제목: {post.title}\n\n바로가기: {post_url}"
                send_email(subject, emails, body)
            return redirect(url_for('post.post_detail', post_id=post_id))
    return render_template('post_detail.html', post=post, user=author, comments=comments, nick_map=nick_map)

@post_bp.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    if not post:
        flash('글을 찾을 수 없습니다.')
        return redirect(url_for('post.index'))
    if post.user_id != session['user_id'] and not session.get('is_admin'):
        flash('삭제 권한이 없습니다.')
        return redirect(url_for('post.post_detail', post_id=post_id))
    # 글 삭제
    Comment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    flash('글이 삭제되었습니다.')
    return redirect(url_for('post.index')) 