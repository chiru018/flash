from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from waitress import serve
import logging
import sys

# ======================= Setup Logging =======================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("flask_logs.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask(__name__)
app.secret_key = 'your_very_secure_secret_key'  # Update this in production
CORS(app)

# ======================= MySQL Connection =======================
def get_db():
    try:
        db = mysql.connector.connect(
            host='localhost',
            user='root',
            password='3011',
            database='attendancesystem'
        )
        app.logger.info("Connected to MySQL database.")
        return db
    except mysql.connector.Error as err:
        app.logger.error(f"MySQL connection error: {err}")
        raise

# ======================= Log All Routes =======================
@app.before_first_request
def log_routes():
    for rule in app.url_map.iter_rules():
        app.logger.info(f"URL: {rule} -> {rule.endpoint}")

# ======================= Home Page =======================
@app.route('/')
def index():
    if 'student_id' in session:
        return redirect('/student_dashboard')
    elif 'teacher_id' in session:
        return redirect('/teacher_dashboard')
    return render_template('index.html')

# ======================= Student Register =======================
@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO students (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
            db.commit()
            db.close()
            app.logger.info(f"Student registered: {name}")
            return redirect('/student_login')
        except mysql.connector.Error as e:
            app.logger.error(f"Student registration error: {e}")
            return f"Error: {e}"
    return render_template('student_register.html')

# ======================= Student Login =======================
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM students WHERE email=%s", (email,))
        student = cursor.fetchone()
        db.close()

        if student and check_password_hash(student[3], password):
            session['student_id'] = student[0]
            session['student_name'] = student[1]
            app.logger.info(f"Student logged in: {student[1]}")
            return redirect(url_for('student_dashboard'))
        else:
            app.logger.warning(f"Failed student login for email: {email}")
            return "Invalid credentials. <a href='/student_login'>Try again</a>"
    return render_template('student_login.html')

# ======================= Student Dashboard =======================
@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect('/student_login')

    sid = session['student_id']
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id=%s AND status='Present'", (sid,))
    present_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id=%s", (sid,))
    total_days = cursor.fetchone()[0]

    percentage = (present_count / total_days * 100) if total_days > 0 else 0

    cursor.execute("SELECT date, status FROM attendance WHERE student_id=%s ORDER BY date DESC", (sid,))
    attendances = cursor.fetchall()

    db.close()
    return render_template('student_dashboard.html', percentage=percentage, attendances=attendances)

# ======================= Student Logout =======================
@app.route('/student_logout')
def student_logout():
    session.pop('student_id', None)
    session.pop('student_name', None)
    app.logger.info("Student logged out successfully.")
    return redirect(url_for('index'))

# ======================= Teacher Login =======================
@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        code = request.form['code']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM teachers WHERE email=%s AND code=%s", (email, code))
        teacher = cursor.fetchone()
        db.close()

        if teacher and check_password_hash(teacher[3], password):
            session['teacher_id'] = teacher[0]
            session['teacher_name'] = teacher[1]
            app.logger.info(f"Teacher logged in: {teacher[1]}")
            return redirect(url_for('teacher_dashboard'))
        else:
            app.logger.warning(f"Failed teacher login for email: {email}")
            return "Invalid credentials. <a href='/teacher_login'>Try again</a>"
    return render_template('teacher_login.html')

# ======================= Teacher Register =======================
@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        code = request.form['code']

        if code != 'T-001':
            return "Invalid teacher code. The code must be T-001. <a href='/teacher_register'>Try again</a>"

        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO teachers (name, email, password, code) VALUES (%s, %s, %s, %s)", (name, email, password, code))
            db.commit()
            db.close()
            app.logger.info(f"Teacher registered: {name}")
            return redirect('/teacher_login')
        except mysql.connector.Error as e:
            app.logger.error(f"Teacher registration error: {e}")
            return f"Error: {e}"

    return render_template('teacher_register.html')

# ======================= Teacher Dashboard =======================
@app.route('/teacher_dashboard', methods=['GET', 'POST'])
def teacher_dashboard():
    if 'teacher_id' not in session:
        return redirect('/teacher_login')

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        student_id = request.form['student_id']
        date = request.form['date']
        status = request.form['status']
        cursor.execute("INSERT INTO attendance (student_id, date, status) VALUES (%s, %s, %s)", (student_id, date, status))
        db.commit()

    cursor.execute("SELECT id, name, email FROM students")
    students = cursor.fetchall()

    cursor.execute("""
        SELECT s.name, a.date, a.status, a.id
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        ORDER BY a.date DESC
    """)
    records = cursor.fetchall()
    db.close()

    return render_template('teacher_dashboard.html', students=students, records=records)

# ======================= Teacher Logout =======================
@app.route('/teacher_logout')
def teacher_logout():
    session.pop('teacher_id', None)
    session.pop('teacher_name', None)
    app.logger.info("Teacher logged out successfully.")
    return redirect(url_for('index'))

# ======================= Run with Waitress =======================
if __name__ == '__main__':
    try:
        conn = get_db()
        if conn.is_connected():
            app.logger.info("Verified MySQL connection.")
        conn.close()
    except mysql.connector.Error as err:
        app.logger.error(f"MySQL connection failed: {err}")

    serve(app, host='0.0.0.0', port=5000)
