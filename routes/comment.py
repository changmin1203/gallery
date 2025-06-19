from flask import Blueprint, redirect, url_for, session, flash
from models import db, Comment
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('로그인이 필요합니다.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

comment_bp = Blueprint('comment', __name__)

@comment_bp.route('/delete_comment/<int:comment_id>/<int:post_id>')
@login_required
def delete_comment(comment_id, post_id):
    comment = Comment.query.get(comment_id)
    if not comment:
        flash('댓글을 찾을 수 없습니다.')
        return redirect(url_for('post.post_detail', post_id=post_id))
    if comment.user_id != session['user_id'] and not session.get('is_admin'):
        flash('삭제 권한이 없습니다.')
        return redirect(url_for('post.post_detail', post_id=post_id))
    db.session.delete(comment)
    db.session.commit()
    flash('댓글이 삭제되었습니다.')
    return redirect(url_for('post.post_detail', post_id=post_id)) 