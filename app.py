from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------- DATABASE ----------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# ---------- MAIL CONFIG ----------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'studenthelphub.project@gmail.com'
app.config['MAIL_PASSWORD'] = 'pudkzgbgifkpoqmr'
app.config['MAIL_DEFAULT_SENDER'] = 'studenthelphub.project@gmail.com'

mail = Mail(app)

# ---------- DATABASE MODELS ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))

    study_seconds = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(200))
    subject = db.Column(db.String(100))
    status = db.Column(db.Integer, default=0)  # 0 = pending, 1 = done
    user_id = db.Column(db.Integer)

    username = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    task_date = db.Column(db.Date, default=datetime.utcnow)
    deadline = db.Column(db.Date)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_text = db.Column(db.Text)
    user_id = db.Column(db.Integer)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150))
    user_id = db.Column(db.Integer)


LEVELS = {
    1: 500,
    2: 1500,
    3: 3000,
    4: 6000
}

# ---------- ROUTES ----------
@app.route('/')
def index():
    return render_template("index.html")


# ---------- REGISTER ----------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first():
            return "User already exists ❌"

        hashed = generate_password_hash(password)

        db.session.add(User(
            username=name,
            email=email,
            password=hashed
        ))
        db.session.commit()

        return redirect('/login')

    return render_template("register.html")


# ---------- LOGIN ----------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if 'attempts' not in session:
            session['attempts'] = 0

        if session.get('lock_time'):
            if datetime.now() < session['lock_time']:
                return "Account locked ⛔ Try again later"
            else:
                session.pop('lock_time')
                session['attempts'] = 0

        if user and check_password_hash(user.password, password):
            session['user'] = user.id
            session['attempts'] = 0

            msg = Message(
                'Login Alert',
                recipients=[email]
            )
            msg.body = "You logged in successfully."

            try:
                mail.send(msg)
            except Exception as e:
                print("Mail failed:", e)

            return redirect('/home')

        session['attempts'] += 1
        remaining = 3 - session['attempts']

        if session['attempts'] >= 3:
            session['lock_time'] = datetime.now() + timedelta(minutes=2)
            return "Too many attempts ⛔ Locked for 2 minutes"

        return f"Invalid credentials ❌ Attempts left: {remaining}"

    return render_template("login.html")


# ---------- HOME ----------
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/login')

    user = User.query.get(session['user'])

    tasks = Task.query.filter_by(user_id=user.id).all()
    notes = Note.query.filter_by(user_id=user.id).all()
    cart = CartItem.query.filter_by(user_id=user.id).all()

    max_points = LEVELS.get(user.level, 500)
    progress = min(int((user.points / max_points) * 100), 100)

    return render_template(
        "home.html",
        user=user,
        tasks=tasks,
        notes=notes,
        cart=cart,
        progress=progress,
        max_points=max_points
    )


# ---------- ADD TASK ----------
@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user' not in session:
        return redirect('/login')

    task = request.form.get("task")
    if not task:
        return redirect('/home')

    user = User.query.get(session['user'])

    date_str = request.form.get("task_date")
    task_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.utcnow()

    deadline_str = request.form.get("deadline")
    deadline = datetime.strptime(deadline_str, "%Y-%m-%d") if deadline_str else None

    db.session.add(Task(
        task_name=task,
        user_id=user.id,
        username=user.username,
        task_date=task_date,
        deadline=deadline
    ))

    db.session.commit()
    return redirect('/home')


# ---------- TOGGLE TASK ----------
@app.route('/toggle_task/<int:id>')
def toggle_task(id):
    task = Task.query.get(id)

    task.status = 1 if task.status == 0 else 0

    db.session.commit()
    return redirect('/home')


# ---------- DELETE TASK ----------
@app.route('/delete_task/<int:id>')
def delete_task(id):
    Task.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect('/home')


# ---------- NOTES ----------
@app.route('/add_note', methods=['POST'])
def add_note():
    if 'user' not in session:
        return redirect('/login')

    note = request.form.get("note")
    db.session.add(Note(note_text=note, user_id=session['user']))
    db.session.commit()

    return redirect('/home')


@app.route('/delete_note/<int:id>')
def delete_note(id):
    Note.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect('/home')


# ---------- CART ----------
@app.route('/add_cart', methods=['POST'])
def add_cart():
    if 'user' not in session:
        return redirect('/login')

    product = request.form.get("product")
    db.session.add(CartItem(product_name=product, user_id=session['user']))
    db.session.commit()

    return redirect('/home')


@app.route('/delete_cart/<int:id>')
def delete_cart(id):
    CartItem.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect('/home')


# ---------- CALENDAR ----------
from datetime import date

@app.route('/calendar')
def calendar():
    if 'user' not in session:
        return redirect('/login')

    tasks = Task.query.filter_by(user_id=session['user']).all()

    calendar_data = {}

    for t in tasks:
        day = t.task_date.strftime("%d %b %Y")

        if day not in calendar_data:
            calendar_data[day] = []

        calendar_data[day].append(t)

    return render_template(
        "calendar.html",
        calendar_data=calendar_data,
        current_date=date.today()   # ✅ IMPORTANT
    )


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------- INIT DB ----------
with app.app_context():
    db.create_all()


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)