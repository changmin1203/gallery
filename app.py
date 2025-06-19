from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
DATA_FILE = 'data.json'

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

# 메인 페이지: 사진 전시
def get_images():
    data = load_data()
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    images = []
    for f in files:
        if allowed_file(f):
            info = data.get(f, {"title": "", "desc": ""})
            images.append({"filename": f, "title": info.get("title", ""), "desc": info.get("desc", "")})
    return images

@app.route('/')
def index():
    images = get_images()
    return render_template('index.html', images=images)

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
            data[filename] = {"title": title, "desc": desc}
            save_data(data)
            return redirect(url_for('index'))
    return render_template('upload.html')

# 업로드된 이미지 제공
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 이미지 상세 페이지
@app.route('/detail/<filename>')
def image_detail(filename):
    data = load_data()
    if filename in data:
        image_info = data[filename]
        image_info['filename'] = filename
        return render_template('detail.html', image=image_info)
    return redirect(url_for('index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
