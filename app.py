from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, flash, abort
import os
from werkzeug.utils import secure_filename
import json
from datetime import datetime
from flask_session import Session
import bcrypt
import cloudinary
import cloudinary.uploader
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, SECRET_KEY, USE_LOCAL_DB
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

if USE_LOCAL_DB:
    from flask_sqlalchemy import SQLAlchemy
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'local.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(app)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        nickname = db.Column(db.String(80), unique=True, nullable=False)
        password_hash = db.Column(db.String(200), nullable=False)
        is_admin = db.Column(db.Boolean, default=False)
    class Post(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        title = db.Column(db.String(200))
        description = db.Column(db.Text)
        image_filenames = db.Column(db.Text)  # comma-separated
    class Comment(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        text = db.Column(db.Text)
    with app.app_context():
        db.create_all()
else:
    # Supabase 연결
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cloudinary 연결
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# Render의 쓰기 가능한 디렉토리 사용
if os.environ.get('RENDER'):
    BASE_DIR = '/opt/render/project/src'
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
COMMENTS_FILE = os.path.join(BASE_DIR, 'comments.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# 필요한 디렉토리와 파일 생성
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not os.path.exists(COMMENTS_FILE):
        with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
except Exception as e:
    print(f"Error creating directories/files: {str(e)}")

# 업로드 허용 확장자 체크
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_comments():
    if not os.path.exists(COMMENTS_FILE):
        return {}
    with open(COMMENTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_comments(comments):
    with open(COMMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)

# 메인 페이지: 이미지만 전시
def get_images():
    try:
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            return []
        
        data = load_data()
        files = os.listdir(app.config['UPLOAD_FOLDER'])
        images = []
        for f in files:
            if allowed_file(f):
                info = data.get(f, {"title": "", "desc": ""})
                images.append({
                    "filename": f,
                    "title": info.get("title", ""),
                    "desc": info.get("desc", "")
                })
        return images
    except Exception as e:
        print(f"Error in get_images: {str(e)}")
        return []

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if USE_LOCAL_DB:
        posts = Post.query.order_by(Post.id.desc()).all()
        # SQLite: image_filenames는 comma-separated string
        for post in posts:
            post.image_urls = post.image_filenames.split(',') if post.image_filenames else []
        return render_template('index.html', posts=posts)
    else:
        res = supabase.table('posts').select('*').order('id', desc=True).execute()
        posts = res.data if res.data else []
        return render_template('index.html', posts=posts)

@app.route('/post/<post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    if USE_LOCAL_DB:
        post = Post.query.get(post_id)
        if not post:
            flash('글을 찾을 수 없습니다.')
            return redirect(url_for('index'))
        user = User.query.get(post.user_id)
        post.image_urls = post.image_filenames.split(',') if post.image_filenames else []
        comments = Comment.query.filter_by(post_id=post_id).all()
        # 댓글 닉네임 매핑
        nick_map = {u.id: u.nickname for u in User.query.filter(User.id.in_([c.user_id for c in comments])).all()}
        # 댓글 작성
        if request.method == 'POST' and 'user_id' in session:
            text = request.form.get('text', '').strip()
            if text:
                comment = Comment(post_id=post_id, user_id=session['user_id'], text=text)
                db.session.add(comment)
                db.session.commit()
                flash('댓글이 등록되었습니다!')
                return redirect(url_for('post_detail', post_id=post_id))
        return render_template('post_detail.html', post=post, user=user, comments=comments, nick_map=nick_map)
    else:
        res = supabase.table('posts').select('*').eq('id', post_id).single().execute()
        post = res.data if res.data else None
        if not post:
            flash('글을 찾을 수 없습니다.')
            return redirect(url_for('index'))
        user = None
        if post.get('user_id'):
            user_res = supabase.table('users').select('nickname').eq('id', post['user_id']).single().execute()
            user = user_res.data if user_res.data else None
        comments = supabase.table('comments').select('*').eq('post_id', post_id).order('id').execute().data or []
        user_ids = list(set([c['user_id'] for c in comments if 'user_id' in c]))
        nick_map = {}
        if user_ids:
            user_rows = supabase.table('users').select('id', 'nickname').in_('id', user_ids).execute().data
            if user_rows:
                nick_map = {u['id']: u['nickname'] for u in user_rows}
        if request.method == 'POST' and 'user_id' in session:
            text = request.form.get('text', '').strip()
            if text:
                comment_data = {'post_id': post_id, 'user_id': session['user_id'], 'text': text}
                supabase.table('comments').insert(comment_data).execute()
                flash('댓글이 등록되었습니다!')
                return redirect(url_for('post_detail', post_id=post_id))
        return render_template('post_detail.html', post=post, user=user, comments=comments, nick_map=nick_map)

# 이미지 업로드
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password != 'Ckdals12!':
            error = '비밀번호가 올바르지 않습니다.'
            return render_template('upload.html', error=error)
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        title = request.form.get('title', '')
        desc = request.form.get('desc', '')
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # 제목/설명 저장
            data = load_data()
            data[filename] = {
                "title": title, 
                "desc": desc,
                "timestamp": datetime.now().isoformat()
            }
            save_data(data)
            return redirect(url_for('index'))
    return render_template('upload.html', error=error)

# 댓글 추가 (상세 페이지용)
@app.route('/add_comment/<filename>', methods=['POST'])
def add_comment(filename):
    text = request.form.get('text', '')
    author = request.form.get('author', 'Anonymous')
    
    if text.strip():
        comments = load_comments()
        if filename not in comments:
            comments[filename] = []
        comment_id = f"comment_{len(comments[filename]) + 1}_{int(datetime.now().timestamp())}"
        comments[filename].append({
            "id": comment_id,
            "text": text,
            "author": author,
            "timestamp": datetime.now().isoformat()
        })
        save_comments(comments)
    
    return redirect(url_for('image_detail', filename=filename))

# 이미지 삭제
@app.route('/delete_image/<filename>')
def delete_image(filename):
    # 파일 삭제
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # 데이터에서도 삭제
    data = load_data()
    if filename in data:
        del data[filename]
        save_data(data)
    
    return redirect(url_for('index'))

# 댓글 삭제 (상세 페이지용)
@app.route('/delete_comment/<comment_id>/<post_id>')
@login_required
def delete_comment(comment_id, post_id):
    if USE_LOCAL_DB:
        comment = Comment.query.get(comment_id)
        if not comment:
            flash('댓글을 찾을 수 없습니다.')
            return redirect(url_for('post_detail', post_id=post_id))
        if comment.user_id != session['user_id'] and not session.get('is_admin'):
            flash('삭제 권한이 없습니다.')
            return redirect(url_for('post_detail', post_id=post_id))
        db.session.delete(comment)
        db.session.commit()
        flash('댓글이 삭제되었습니다.')
        return redirect(url_for('post_detail', post_id=post_id))
    else:
        comment = supabase.table('comments').select('*').eq('id', comment_id).single().execute().data
        if not comment:
            flash('댓글을 찾을 수 없습니다.')
            return redirect(url_for('post_detail', post_id=post_id))
        if comment['user_id'] != session['user_id'] and not session.get('is_admin'):
            flash('삭제 권한이 없습니다.')
            return redirect(url_for('post_detail', post_id=post_id))
        supabase.table('comments').delete().eq('id', comment_id).execute()
        flash('댓글이 삭제되었습니다.')
        return redirect(url_for('post_detail', post_id=post_id))

# 이미지 상세 페이지
@app.route('/detail/<filename>')
def image_detail(filename):
    data = load_data()
    comments = load_comments()
    if filename in data:
        image_info = data[filename]
        image_info['filename'] = filename
        image_comments = comments.get(filename, [])
        return render_template('detail.html', image=image_info, comments=image_comments)
    return redirect(url_for('index'))

# 업로드된 이미지 제공
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete_confirm/<filename>', methods=['GET', 'POST'])
def delete_confirm(filename):
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == 'Ckdals12!':
            # 실제 삭제
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            data = load_data()
            if filename in data:
                del data[filename]
                save_data(data)
            return redirect(url_for('index'))
        else:
            error = '비밀번호가 올바르지 않습니다.'
    return render_template('delete_confirm.html', filename=filename, error=error)

# 회원가입 예시
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        nickname = request.form['nickname']
        password = request.form['password']
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        # Supabase에 저장
        data = {
            "email": email,
            "nickname": nickname,
            "password_hash": hashed.decode('utf-8'),
            "is_admin": False
        }
        supabase.table('users').insert(data).execute()
        flash('회원가입 완료! 로그인 해주세요.')
        return redirect(url_for('login'))
    return render_template('register.html')

# 로그인 예시
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        res = supabase.table('users').select('*').eq('email', email).execute()
        if res.data:
            user = res.data[0]
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                session['user_id'] = user['id']
                session['nickname'] = user['nickname']
                session['is_admin'] = user['is_admin']
                flash('로그인 성공!')
                return redirect(url_for('index'))
        flash('이메일 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.clear()
    flash('로그아웃 되었습니다.')
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if USE_LOCAL_DB:
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            files = request.files.getlist('images')
            filenames = []
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    filenames.append(filename)
            post = Post(user_id=session['user_id'], title=title, description=description, image_filenames=','.join(filenames))
            db.session.add(post)
            db.session.commit()
            flash('글이 등록되었습니다!')
            return redirect(url_for('index'))
        return render_template('create_post.html')
    else:
        if request.method == 'POST':
            title = request.form['title']
            description = request.form['description']
            files = request.files.getlist('images')
            image_urls = []
            for file in files:
                if file and file.filename:
                    upload_result = cloudinary.uploader.upload(file)
                    image_urls.append(upload_result['secure_url'])
            data = {"user_id": session['user_id'], "title": title, "description": description, "image_urls": image_urls}
            supabase.table('posts').insert(data).execute()
            flash('글이 등록되었습니다!')
            return redirect(url_for('index'))
        return render_template('create_post.html')

@app.route('/delete_post/<post_id>')
@login_required
def delete_post(post_id):
    post = supabase.table('posts').select('*').eq('id', post_id).single().execute().data
    if not post:
        flash('글을 찾을 수 없습니다.')
        return redirect(url_for('index'))
    if post['user_id'] != session['user_id'] and not session.get('is_admin'):
        flash('삭제 권한이 없습니다.')
        return redirect(url_for('post_detail', post_id=post_id))
    # 글 삭제
    supabase.table('posts').delete().eq('id', post_id).execute()
    # 댓글도 함께 삭제
    supabase.table('comments').delete().eq('post_id', post_id).execute()
    flash('글이 삭제되었습니다.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
