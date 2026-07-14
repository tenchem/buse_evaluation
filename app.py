import os
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_FILE = "database.db"
ADMIN_PASSWORD = "BuseChairperson2026"  # Static password for creating sessions & dashboard access

# The exact 23 questions from the BUSE Peer Assessment / Evaluation standard
BUSE_QUESTIONS = [
    {"id": 1, "text": "Punctuality and regularity in attending lectures/practicals."},
    {"id": 2, "text": "Effective and structured introduction of lesson topics."},
    {"id": 3, "text": "Clarity of delivery, explanation, and pronunciation of concepts."},
    {"id": 4, "text": "Logical sequencing and organization of content."},
    {"id": 5, "text": "Audibility and vocal variety during lecturing."},
    {"id": 6, "text": "Use of appropriate examples and illustrations to aid understanding."},
    {"id": 7, "text": "Command of subject matter and technical accuracy."},
    {"id": 8, "text": "Responsiveness to students' questions and interactive inquiries."},
    {"id": 9, "text": "Integration of relevant modern teaching aids (e.g., slides, whiteboard, LMS)."},
    {"id": 10, "text": "Clarity in outlining the course objectives and learning outcomes."},
    {"id": 11, "text": "Fair and constructive treatment of all students in the classroom."},
    {"id": 12, "text": "Ability to command attention, maintain class discipline, and manage time."},
    {"id": 13, "text": "Pacing of lectures to match different student comprehension speeds."},
    {"id": 14, "text": "Encouraging critical thinking, student participation, and team discussions."},
    {"id": 15, "text": "Appropriate dressing and professional grooming."},
    {"id": 16, "text": "Availability and accessibility for consultation outside lectures."},
    {"id": 17, "text": "Provision of timely feedback on assessments and tests."},
    {"id": 18, "text": "Alignment of assessments with the course content and syllabus outline."},
    {"id": 19, "text": "Encouraging innovation, analytical skills, and industrial application."},
    {"id": 20, "text": "Consistency of the lecturer's teaching with Education 5.0 pillars."},
    {"id": 21, "text": "Maintenance of student-lecturer professional boundaries."},
    {"id": 22, "text": "Effective use of the local university environment or resources for learning."},
    {"id": 23, "text": "Overall effectiveness of the lecturer in delivering the course content."}
]


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Table for sessions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pin TEXT NOT NULL UNIQUE,
            lecturer_name TEXT NOT NULL,
            course_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    # Table for response coursework and general metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            topic_coverage TEXT,
            num_assignments INTEGER,
            num_tests INTEGER,
            general_comments TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES evaluation_sessions(id)
        )
    ''')
    # Table for individual item scores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER,
            question_num INTEGER,
            score INTEGER,
            FOREIGN KEY(response_id) REFERENCES responses(id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # Student submitting session PIN
        entered_pin = request.form.get('pin', '').strip()
        conn = get_db_connection()
        session_data = conn.execute(
            'SELECT * FROM evaluation_sessions WHERE pin = ? AND is_active = 1',
            (entered_pin,)
        ).fetchone()
        conn.close()

        if session_data:
            session['active_session_id'] = session_data['id']
            session['active_pin'] = session_data['pin']
            session['lecturer_name'] = session_data['lecturer_name']
            session['course_code'] = session_data['course_code']
            return redirect(url_for('evaluation_form'))
        else:
            flash("Invalid or inactive Session PIN. Please verify with your peer leader.", "danger")
            return redirect(url_for('home'))

    return render_template('login.html')


@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('admin_password', '').strip()
    if password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        flash("Logged in successfully as Admin/Chairperson.", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Incorrect administrator password.", "danger")
        return redirect(url_for('home'))


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Admin logged out successfully.", "info")
    return redirect(url_for('home'))


@app.route('/admin/session/create', methods=['POST'])
def create_session():
    if not session.get('admin_logged_in'):
        return redirect(url_for('home'))

    lecturer = request.form.get('lecturer_name', '').strip()
    course = request.form.get('course_code', '').strip()

    if not lecturer or not course:
        flash("Lecturer name and Course code are required.", "danger")
        return redirect(url_for('dashboard'))

    # Generate random unique 4-digit PIN
    conn = get_db_connection()
    while True:
        pin = str(random.randint(1000, 9999))
        existing = conn.execute('SELECT 1 FROM evaluation_sessions WHERE pin = ?', (pin,)).fetchone()
        if not existing:
            break

    # Automatically deactivate other sessions of identical criteria to avoid dual evaluation tracks
    conn.execute('UPDATE evaluation_sessions SET is_active = 0 WHERE course_code = ?', (course,))

    conn.execute(
        'INSERT INTO evaluation_sessions (pin, lecturer_name, course_code) VALUES (?, ?, ?)',
        (pin, lecturer, course)
    )
    conn.commit()
    conn.close()

    flash(f"Successfully generated Evaluation Session! PIN: {pin}", "success")
    return redirect(url_for('dashboard'))


@app.route('/admin/session/toggle/<int:session_id>')
def toggle_session(session_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('home'))
    conn = get_db_connection()
    current = conn.execute('SELECT is_active FROM evaluation_sessions WHERE id = ?', (session_id,)).fetchone()
    if current:
        new_state = 0 if current['is_active'] == 1 else 1
        conn.execute('UPDATE evaluation_sessions SET is_active = ? WHERE id = ?', (new_state, session_id))
        conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/evaluation', methods=['GET', 'POST'])
def evaluation_form():
    if 'active_session_id' not in session:
        flash("Access Denied: Please enter a valid evaluation session PIN.", "danger")
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Collect coursework metrics
        topic_coverage = request.form.get('topic_coverage', '')
        num_assignments = request.form.get('num_assignments', 0)
        num_tests = request.form.get('num_tests', 0)
        general_comments = request.form.get('general_comments', '').strip()

        conn = get_db_connection()
        # Save response root
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO responses (session_id, topic_coverage, num_assignments, num_tests, general_comments) VALUES (?, ?, ?, ?, ?)',
            (session['active_session_id'], topic_coverage, num_assignments, num_tests, general_comments)
        )
        response_id = cursor.lastrowid

        # Save exact 23 question choices
        for q in BUSE_QUESTIONS:
            score = request.form.get(f"q_{q['id']}")
            if score:
                cursor.execute(
                    'INSERT INTO question_scores (response_id, question_num, score) VALUES (?, ?, ?)',
                    (response_id, q['id'], int(score))
                )

        conn.commit()
        conn.close()

        # Remove student session after singular submission
        session.pop('active_session_id', None)
        session.pop('active_pin', None)
        session.pop('lecturer_name', None)
        session.pop('course_code', None)

        return render_template('login.html',
                               success_msg="Thank you! Your peer evaluation has been submitted successfully.")

    return render_template('evaluation.html', questions=BUSE_QUESTIONS)


@app.route('/admin/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        flash("You must log in to view the dashboard.", "warning")
        return redirect(url_for('home'))

    conn = get_db_connection()
    sessions = conn.execute('SELECT * FROM evaluation_sessions ORDER BY created_at DESC').fetchall()

    # Calculate performance metrics for all lecturers
    lecturers_data = {}

    # Get all responses grouped by session
    db_responses = conn.execute('''
        SELECT r.id, r.topic_coverage, r.num_assignments, r.num_tests, r.general_comments, 
               es.lecturer_name, es.course_code 
        FROM responses r
        JOIN evaluation_sessions es ON r.session_id = es.id
    ''').fetchall()

    for resp in db_responses:
        key = (resp['lecturer_name'], resp['course_code'])
        if key not in lecturers_data:
            lecturers_data[key] = {
                "lecturer_name": resp['lecturer_name'],
                "course_code": resp['course_code'],
                "submissions_count": 0,
                "topic_coverages": [],
                "assignments_sum": 0,
                "tests_sum": 0,
                "comments": [],
                "scores_by_question": {q['id']: [] for q in BUSE_QUESTIONS}
            }

        lecturers_data[key]["submissions_count"] += 1
        if resp['topic_coverage']:
            lecturers_data[key]["topic_coverages"].append(resp['topic_coverage'])
        lecturers_data[key]["assignments_sum"] += resp['num_assignments'] if resp['num_assignments'] else 0
        lecturers_data[key]["tests_sum"] += resp['num_tests'] if resp['num_tests'] else 0
        if resp['general_comments']:
            lecturers_data[key]["comments"].append(resp['general_comments'])

        # Get individual question ratings
        scores = conn.execute('SELECT question_num, score FROM question_scores WHERE response_id = ?',
                              (resp['id'],)).fetchall()
        for s in scores:
            q_num = s['question_num']
            if q_num in lecturers_data[key]["scores_by_question"]:
                lecturers_data[key]["scores_by_question"][q_num].append(s['score'])

    # Compile computed aggregations
    processed_lecturers = []
    for key, data in lecturers_data.items():
        avg_scores = {}
        grand_total = 0
        questions_answered = 0

        for q in BUSE_QUESTIONS:
            scores_list = data["scores_by_question"][q['id']]
            if scores_list:
                avg = round(sum(scores_list) / len(scores_list), 2)
                avg_scores[q['id']] = avg
                grand_total += sum(scores_list)
                questions_answered += len(scores_list)
            else:
                avg_scores[q['id']] = "N/A"

        overall_avg = round(grand_total / questions_answered, 2) if questions_answered > 0 else "N/A"

        # Calculate coverage mode
        coverages = data["topic_coverages"]
        mode_coverage = max(set(coverages), key=coverages.count) if coverages else "No Data"

        avg_assignments = round(data["assignments_sum"] / data["submissions_count"], 1) if data[
                                                                                               "submissions_count"] > 0 else 0
        avg_tests = round(data["tests_sum"] / data["submissions_count"], 1) if data["submissions_count"] > 0 else 0

        processed_lecturers.append({
            "lecturer_name": data["lecturer_name"],
            "course_code": data["course_code"],
            "submissions_count": data["submissions_count"],
            "overall_average": overall_avg,
            "avg_assignments": avg_assignments,
            "avg_tests": avg_tests,
            "mode_coverage": mode_coverage,
            "avg_scores": avg_scores,
            "comments": data["comments"]
        })

    conn.close()
    return render_template('dashboard.html', sessions=sessions, lecturers=processed_lecturers, questions=BUSE_QUESTIONS)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)