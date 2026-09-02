import os
from dotenv import load_dotenv
from datetime import date
from functools import wraps

load_dotenv()

load_dotenv()

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

# Secret key
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key-for-production"
)

# Database
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Some hosting providers may provide postgres://
    # instead of postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Local development database
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///silambam.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# DATABASE MODELS
# =========================================================

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    belt = db.Column(db.String(50), nullable=False)
    join_date = db.Column(db.String(20), nullable=False)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )
    attendance_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    student = db.relationship("Student")


class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    student = db.relationship("Student")


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    achievement_date = db.Column(db.String(20), nullable=False)

    student = db.relationship("Student")


# =========================================================
# LOGIN PROTECTION
# =========================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "admin_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(
            admin.password_hash,
            password
        ):

            session.clear()

            session["admin_id"] = admin.id
            session["admin_username"] = admin.username

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    total_students = Student.query.count()

    today = date.today().strftime("%Y-%m-%d")

    present_today = Attendance.query.filter_by(
        attendance_date=today,
        status="Present"
    ).count()

    fees_collected = db.session.query(
        db.func.sum(Fee.amount)
    ).filter(
        Fee.status == "Paid"
    ).scalar() or 0

    achievements_count = Achievement.query.count()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        fees_collected=fees_collected,
        achievements_count=achievements_count
    )


# =========================================================
# STUDENTS
# =========================================================

@app.route("/students")
@login_required
def students_page():

    students = Student.query.order_by(
        Student.id.desc()
    ).all()

    return render_template(
        "students.html",
        students=students
    )


@app.route("/add_student", methods=["POST"])
@login_required
def add_student():

    name = request.form.get("name", "").strip()
    age = request.form.get("age", "").strip()
    phone = request.form.get("phone", "").strip()
    belt = request.form.get("belt", "").strip()
    join_date = request.form.get("join_date", "").strip()

    if not name or not age or not phone or not belt or not join_date:
        flash("Please fill all student details.", "error")
        return redirect(url_for("students_page"))

    try:
        age = int(age)
    except ValueError:
        flash("Age must be a number.", "error")
        return redirect(url_for("students_page"))

    student = Student(
        name=name,
        age=age,
        phone=phone,
        belt=belt,
        join_date=join_date
    )

    db.session.add(student)
    db.session.commit()

    flash("Student added successfully.", "success")

    return redirect(url_for("students_page"))


@app.route("/delete_student/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):

    student = db.get_or_404(Student, student_id)

    Attendance.query.filter_by(
        student_id=student.id
    ).delete()

    Fee.query.filter_by(
        student_id=student.id
    ).delete()

    Achievement.query.filter_by(
        student_id=student.id
    ).delete()

    db.session.delete(student)

    db.session.commit()

    flash("Student deleted.", "success")

    return redirect(url_for("students_page"))


# =========================================================
# ATTENDANCE
# =========================================================

@app.route("/attendance")
@login_required
def attendance_page():

    students = Student.query.order_by(
        Student.name
    ).all()

    selected_date = request.args.get(
        "date",
        date.today().strftime("%Y-%m-%d")
    )

    return render_template(
        "attendance.html",
        students=students,
        selected_date=selected_date
    )


@app.route("/save_attendance", methods=["POST"])
@login_required
def save_attendance():

    attendance_date = request.form.get(
        "attendance_date"
    )

    students = Student.query.all()

    for student in students:

        status = request.form.get(
            f"status_{student.id}",
            "Absent"
        )

        existing = Attendance.query.filter_by(
            student_id=student.id,
            attendance_date=attendance_date
        ).first()

        if existing:
            existing.status = status

        else:
            record = Attendance(
                student_id=student.id,
                attendance_date=attendance_date,
                status=status
            )

            db.session.add(record)

    db.session.commit()

    flash("Attendance saved successfully.", "success")

    return redirect(
        url_for(
            "attendance_page",
            date=attendance_date
        )
    )


# =========================================================
# FEES
# =========================================================

@app.route("/fees")
@login_required
def fees_page():

    students = Student.query.order_by(
        Student.name
    ).all()

    fees = Fee.query.order_by(
        Fee.id.desc()
    ).all()

    return render_template(
        "fees.html",
        students=students,
        fees=fees
    )


@app.route("/add_fee", methods=["POST"])
@login_required
def add_fee():

    student_id = request.form.get("student_id")
    amount = request.form.get("amount")
    payment_date = request.form.get("payment_date")
    status = request.form.get("status", "Paid")

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        flash("Invalid fee amount.", "error")
        return redirect(url_for("fees_page"))

    fee = Fee(
        student_id=int(student_id),
        amount=amount,
        payment_date=payment_date,
        status=status
    )

    db.session.add(fee)
    db.session.commit()

    flash("Fee record added successfully.", "success")

    return redirect(url_for("fees_page"))


# =========================================================
# ACHIEVEMENTS
# =========================================================

@app.route("/achievements")
@login_required
def achievements_page():

    students = Student.query.order_by(
        Student.name
    ).all()

    achievements = Achievement.query.order_by(
        Achievement.id.desc()
    ).all()

    return render_template(
        "achievements.html",
        students=students,
        achievements=achievements
    )


@app.route("/add_achievement", methods=["POST"])
@login_required
def add_achievement():

    student_id = request.form.get("student_id")
    title = request.form.get("title", "").strip()
    description = request.form.get(
        "description",
        ""
    ).strip()

    achievement_date = request.form.get(
        "achievement_date"
    )

    if not title or not achievement_date:
        flash(
            "Achievement title and date are required.",
            "error"
        )

        return redirect(
            url_for("achievements_page")
        )

    achievement = Achievement(
        student_id=int(student_id),
        title=title,
        description=description,
        achievement_date=achievement_date
    )

    db.session.add(achievement)
    db.session.commit()

    flash(
        "Achievement added successfully.",
        "success"
    )

    return redirect(
        url_for("achievements_page")
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    with app.app_context():

        db.create_all()

        # Create admin account only if it doesn't exist
        username = os.environ.get(
            "ADMIN_USERNAME",
            "admin"
        )

        password = os.environ.get(
            "ADMIN_PASSWORD",
            "password"
        )

        admin = Admin.query.filter_by(
            username=username
        ).first()

        if not admin:

            admin = Admin(
                username=username,
                password_hash=generate_password_hash(
                    password
                )
            )

            db.session.add(admin)
            db.session.commit()


initialize_database()


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )