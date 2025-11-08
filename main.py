from flask import Flask, render_template, url_for, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from config import Config
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['SECRET_KEY'] = 'your-secret-key-here'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    user_data = Config.USERS.get(user_id)
    if user_data:
        return User(id=user_id, username=user_id, role=user_data['role'])
    return None

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

    def is_admin(self):
        return self.role == 'admin'

    def is_teacher(self):
        return self.role == 'teacher' or self.role == 'admin'

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    intro = db.Column(db.String(300), nullable=False)
    text = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(1000), default='')
    date = db.Column(db.DateTime, default=datetime.utcnow)
    youtube_id = db.Column(db.String(150), default='')

    def __repr__(self):
        return '<Article %r>' % self.id

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_teacher():
            flash('Доступ разрешен только учителям', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Доступ разрешен только администраторам', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    articles = Article.query.order_by(Article.date.desc()).all()
    return render_template('index.html', articles=articles)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа для учителей и администраторов"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверяем credentials из config
        user_data = Config.USERS.get(username)

        if user_data and user_data['password'] == password:
            user = User(id=username, username=username, role=user_data['role'])
            login_user(user)
            flash(f'Добро пожаловать, {username}!', 'success')

            # Перенаправляем в зависимости от роли
            if user.is_admin():
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('teacher_panel'))
        else:
            flash('Неверный логин или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/teacher')
@login_required
@teacher_required
def teacher_panel():
    """Панель учителя - обзор и управление постами"""
    articles = Article.query.order_by(Article.date.desc()).all()
    return render_template('teacher_panel.html', articles=articles)


@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Панель администратора - полный контроль"""
    articles = Article.query.order_by(Article.date.desc()).all()
    total_articles = len(articles)
    users = Config.USERS

    return render_template('admin_panel.html',
                           articles=articles,
                           total_articles=total_articles,
                           users=users)

def after_request(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' *"
    return response

@app.route('/add-post', methods=["POST", "GET"])
@login_required
@teacher_required
def post():
    if request.method == 'POST':
        title = request.form['title']
        intro = request.form['intro']
        text = request.form['text']
        youtube_id = request.form.get('youtube_id', '').strip()

        image_filename = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                from datetime import datetime
                filename = filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

        article = Article(title=title, intro=intro, text=text, image=image_filename, youtube_id=youtube_id)

        try:
            db.session.add(article)
            db.session.commit()
            return redirect('/')
        except:
            return "При добавлении поста произошла ошибка"
    else:
        return render_template("post-create.html")

@app.route('/posts/<int:id>')
def post_detail(id):
    article = Article.query.get(id)
    return render_template('post_detail.html', article=article)

@app.route('/posts/<int:id>/del')
@login_required
@admin_required
def post_delete(id):
    article = Article.query.get_or_404(id)
    try:
        db.session.delete(article)
        db.session.commit()
        return redirect("/")
    except:
        return "При Удалении поста произошла ошибка"

if __name__ == "__main__":
    app.run(debug=True)