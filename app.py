from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
from werkzeug.utils import secure_filename
import json
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
DATA_FILE = 'data.json'
COMMENTS_FILE = 'comments.json'

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

# 메인 페이지: 사진과 댓글 전시
def get_content():
    data = load_data()
    comments = load_comments()
    
    # 이미지와 댓글을 하나의 리스트로 합치기
    content = []
    
    # 이미지 추가
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    for f in files:
        if allowed_file(f):
            info = data.get(f, {"title": "", "desc": ""})
            content.append({
                "type": "image",
                "filename": f,
                "title": info.get("title", ""),
                "desc": info.get("desc", ""),
                "timestamp": info.get("timestamp", "")
            })
    
    # 댓글 추가
    for comment_id, comment in comments.items():
        content.append({
            "type": "comment",
            "id": comment_id,
            "text": comment.get("text", ""),
            "author": comment.get("author", ""),
            "timestamp": comment.get("timestamp", "")
        })
    
    # 타임스탬프로 정렬 (최신순)
    content.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return content

@app.route('/')
def index():
    content = get_content()
    return render_template('index.html', content=content)

# 이미지 업로드
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
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
    return render_template('upload.html')

# 댓글 추가
@app.route('/add_comment', methods=['POST'])
def add_comment():
    text = request.form.get('text', '')
    author = request.form.get('author', 'Anonymous')
    
    if text.strip():
        comments = load_comments()
        comment_id = f"comment_{len(comments) + 1}_{int(datetime.now().timestamp())}"
        comments[comment_id] = {
            "text": text,
            "author": author,
            "timestamp": datetime.now().isoformat()
        }
        save_comments(comments)
    
    return redirect(url_for('index'))

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

# 댓글 삭제
@app.route('/delete_comment/<comment_id>')
def delete_comment(comment_id):
    comments = load_comments()
    if comment_id in comments:
        del comments[comment_id]
        save_comments(comments)
    
    return redirect(url_for('index'))

# 이미지 상세 페이지
@app.route('/detail/<filename>')
def image_detail(filename):
    data = load_data()
    if filename in data:
        image_info = data[filename]
        image_info['filename'] = filename
        return render_template('detail.html', image=image_info)
    return redirect(url_for('index'))

# 업로드된 이미지 제공
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
