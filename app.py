from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector, os
import requests


app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads/photos/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

from config import db_config

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

ADMIN_USERNAME = "sharma"
ADMIN_PASSWORD = "12"

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT password, role FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        con.close()

        if user and check_password_hash(user[0], password):
            session[user[1]] = username
            return redirect(url_for('teacher_dashboard' if user[1]=='teacher' else 'student_dashboard'))

        flash("Invalid credentials.")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()

    # Fetch messages
    cur.execute("SELECT * FROM messages ORDER BY id DESC")
    messages = cur.fetchall()

    # Fetch voting results (make it explicit)
    cur.execute("SELECT id, title, option_text, votes FROM votes")
    votes = cur.fetchall()

    # Fetch teacher usernames
    cur.execute("SELECT username FROM users WHERE role = 'teacher'")
    teachers = [r[0] for r in cur.fetchall()]

    con.close()
    return render_template(
        'admin_dashboard.html',
        messages=messages,
        teachers=teachers,
        votes=votes
    )


@app.route('/admin/register', methods=['POST'])
def admin_register():
    if not session.get('admin'): return redirect(url_for('login'))

    username = request.form['username']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    standard = request.form.get('standard') if role == 'student' else None

    con = get_db_connection()
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO users (username, password, role, standard) VALUES (%s, %s, %s, %s)",
                    (username, password, role, standard))
        con.commit()
        flash("User registered successfully.")
    except:
        flash("Username already exists.")
    con.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin-message', methods=['POST'])
def admin_message():
    if not session.get('admin'): return redirect(url_for('login'))

    content = request.form['message']
    to = request.form['to']

    con = get_db_connection()
    cur = con.cursor()
    cur.execute("INSERT INTO messages (content, recipient) VALUES (%s, %s)", (content, to))
    con.commit()
    con.close()

    flash("Message sent.")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/create-vote', methods=['GET', 'POST'])
def create_vote():
    if not session.get('admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title'].strip()
        options_raw = request.form['options'].strip()

        # Convert comma-separated options into list
        options = [opt.strip() for opt in options_raw.split(',') if opt.strip()]

        if not title or not options:
            flash("⚠️ Title and options are required.", "warning")
            return redirect(url_for('admin_dashboard'))

        con = get_db_connection()
        cur = con.cursor()

        # 🧹 Delete any old vote data with same title
        cur.execute("DELETE FROM student_votes WHERE vote_title = %s", (title,))
        cur.execute("DELETE FROM vote_options WHERE title = %s", (title,))
        cur.execute("DELETE FROM votes WHERE title = %s", (title,))
        con.commit()

        # 🆕 Insert into vote_options and votes tables
        for opt in options:
            cur.execute("INSERT INTO vote_options (title, option) VALUES (%s, %s)", (title, opt))
            cur.execute("INSERT INTO votes (title, option_text, votes, active) VALUES (%s, %s, 0, 1)", (title, opt))

        con.commit()
        con.close()

        flash("✅ Vote created successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template("admin_create_vote.html")


# @app.route('/admin/stop-vote', methods=['POST'])
# def stop_vote():
#     if not session.get('admin'):
#         return redirect(url_for('login'))

#     title = request.form['title']
#     con = get_db_connection()
#     cur = con.cursor()
#     cur.execute("UPDATE votes SET active=FALSE WHERE title=%s", (title,))
#     con.commit()
#     con.close()

#     flash(f"Voting for '{title}' stopped.")
#     return redirect(url_for('admin_dashboard'))

@app.route('/delete_vote', methods=['POST'])
def delete_vote():
    if not session.get('admin'):
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()

    if not title:
        flash("⚠️ No vote title selected.", "warning")
        return redirect(url_for('admin_dashboard'))

    con = get_db_connection()
    cur = con.cursor()

    # ❌ Remove from all relevant tables
    cur.execute("DELETE FROM student_votes WHERE vote_title = %s", (title,))
    cur.execute("DELETE FROM vote_options WHERE title = %s", (title,))
    cur.execute("DELETE FROM votes WHERE title = %s", (title,))
    
    con.commit()
    con.close()

    flash(f"🗑️ Vote '{title}' deleted successfully.")
    return redirect(url_for('admin_dashboard'))

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'student' not in session:
        return redirect(url_for('login'))

    student = session['student']
    selected_title = request.args.get('title') or request.form.get('title')
    message = None
    voted = False
    options = []

    con = get_db_connection()
    cur = con.cursor()

    # 🔹 Get all vote titles
    cur.execute("SELECT DISTINCT title FROM votes")
    titles = [row[0] for row in cur.fetchall()]

    if selected_title:
        # 🔹 Check if already voted
        cur.execute("""
            SELECT 1 FROM student_votes 
            WHERE username = %s AND vote_title = %s AND option_id IS NOT NULL
        """, (student, selected_title))
        already_voted = cur.fetchone()

        # 🔹 Get options
        cur.execute("SELECT id, option FROM vote_options WHERE title = %s", (selected_title,))
        options = cur.fetchall()

        if request.method == 'POST' and not already_voted:
            option_id = request.form.get('option_id')

            if option_id:
                # Get actual option text
                cur.execute("SELECT option FROM vote_options WHERE id = %s", (option_id,))
                option_row = cur.fetchone()

                if option_row:
                    option_text = option_row[0]

                    # Insert vote
                    cur.execute("""
                        INSERT INTO student_votes (username, vote_title, option_id, voted_at)
                        VALUES (%s, %s, %s, NOW())
                    """, (student, selected_title, option_id))

                    # Increment vote count
                    cur.execute("""
                        UPDATE votes SET votes = votes + 1 
                        WHERE title = %s AND option_text = %s
                    """, (selected_title, option_text))

                    con.commit()
                    message = "✅ Your vote has been submitted."
                    voted = True
                else:
                    message = "❌ Invalid option selected."
            else:
                message = "⚠️ Please select an option to vote."

        elif already_voted:
            message = f"✅ You have already voted for \"{selected_title}\"."
            voted = True

    con.close()

    return render_template("vote.html",
        titles=titles,
        selected_title=selected_title,
        options=options,
        message=message,
        voted=voted
    )

@app.route('/admin/student-votes', methods=['GET', 'POST'])
def view_student_votes():
    if not session.get('admin'):
        return redirect(url_for('login'))

    selected_student = None
    votes = []

    con = get_db_connection()
    cur = con.cursor()

    # Get all student usernames
    cur.execute("SELECT username FROM users WHERE role = 'student'")
    students = [row[0] for row in cur.fetchall()]

    if request.method == 'POST':
        selected_student = request.form.get('student')
    
    
        # ✅ Fetch voting history including timestamp
        cur.execute("""
            SELECT sv.vote_title, vo.option, sv.voted_at
            FROM student_votes sv
            JOIN vote_options vo ON sv.option_id = vo.id
            WHERE sv.username = %s
            ORDER BY sv.voted_at DESC
        """, (selected_student,))
        votes = cur.fetchall()

    con.close()

    return render_template("admin_student_votes.html",
        students=students,
        selected_student=selected_student,
        votes=votes
    )

@app.route('/student/chat', methods=['GET', 'POST'])
def student_chat():
    if 'student' not in session:
        return redirect(url_for('login'))

    response = ""
    if request.method == 'POST':
        user_input = request.form['message']
        try:
            result = requests.post("http://127.0.0.1:11434/api/generate", json={
                "model": "llama3",
                "prompt": user_input,
                "stream": False
            })
            result.raise_for_status()
            data = result.json()
            response = data.get("response", "No response from AI.")
        except Exception as e:
            response = f"Error: {e}"

    return render_template('student_chat.html', response=response)


@app.route('/teacher')
def teacher_dashboard():
    if 'teacher' not in session:
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()

    # Fetch study materials
    cur.execute("SELECT * FROM materials")
    materials = cur.fetchall()

    # Fetch quizzes
    cur.execute("SELECT * FROM quizzes")
    quizzes = cur.fetchall()

    # Fetch admin messages
    cur.execute("SELECT content FROM messages WHERE recipient IN ('teacher', 'all')")
    messages = [row[0] for row in cur.fetchall()]

    # Fetch registered students (from admin) — include their uploaded photo if any
    cur.execute("SELECT username, standard, photo FROM users WHERE role='student'")
    students = cur.fetchall()

    con.close()

    return render_template(
        'dashboard.html',
        materials=materials,
        quizzes=quizzes,
        messages=messages,
        students=students
    )


@app.route('/upload-student-photo/<username>', methods=['POST'])
def upload_student_photo(username):
    if 'teacher' not in session:
        return redirect(url_for('login'))

    file = request.files['photo']

    if file:
        filename = secure_filename(f"{username}_{file.filename}")
        save_path = os.path.join('static/uploads/photos/', filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)

        con = get_db_connection()
        cur = con.cursor()
        cur.execute("UPDATE users SET photo=%s WHERE username=%s", (filename, username))
        con.commit()
        con.close()

        flash("Photo uploaded successfully.")

    return redirect(url_for('teacher_dashboard'))


@app.route('/create-quiz', methods=['GET', 'POST'])
def create_quiz():
    if not session.get('teacher'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        questions = request.form.getlist('question')
        a_options = request.form.getlist('a')
        b_options = request.form.getlist('b')
        c_options = request.form.getlist('c')
        d_options = request.form.getlist('d')
        correct_options = request.form.getlist('correct')
        subject = request.form['subject']
        standard = request.form['standard']

        con = get_db_connection()
        cur = con.cursor()

        for i in range(len(questions)):
            cur.execute("""
                INSERT INTO quizzes (question, option1, option2, option3, option4, answer, subject, standard)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                questions[i], a_options[i], b_options[i],
                c_options[i], d_options[i], correct_options[i],
                subject, standard
            ))

        con.commit()
        con.close()

        flash(f"{len(questions)} questions added successfully!")
        return redirect(url_for('teacher_dashboard'))

    return render_template('create_quiz.html')
    
@app.route('/take-quiz', methods=['GET', 'POST'])
def take_quiz():
    if not session.get('student'):
        return redirect(url_for('login'))

    username = session['student']
    con = get_db_connection()
    cur = con.cursor()

    # Get student's own standard
    cur.execute("SELECT standard FROM users WHERE username=%s", (username,))
    result = cur.fetchone()

    if not result:
        flash("Could not fetch your standard.")
        return redirect(url_for('login'))

    student_standard = result[0]

    # Get available subjects for this student's standard from quizzes table
    cur.execute("SELECT DISTINCT subject FROM quizzes WHERE standard=%s", (student_standard,))
    subjects = [row[0] for row in cur.fetchall()]

    if request.method == 'POST':
        name = request.form['name']
        subject = request.form['subject']

        cur.execute("SELECT * FROM quizzes WHERE standard=%s AND subject=%s", (student_standard, subject))
        questions = cur.fetchall()

        con.close()
        return render_template(
            'take_quiz.html',
            questions=questions,
            name=name,
            standard=student_standard,
            subject=subject
        )

    con.close()
    return render_template(
        'take_quiz.html',
        questions=None,
        subjects=subjects,
        standard=student_standard
    )

@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    if not session.get('student'):
        return redirect(url_for('login'))

    # Fetch submitted form data
    name = request.form['name']
    standard = request.form['standard']
    subject = request.form['subject']

    # Collect submitted answers
    answers = {key: value for key, value in request.form.items() if key not in ['name', 'standard', 'subject']}

    con = get_db_connection()
    cur = con.cursor()

    score = 0
    total_questions = len(answers)

    # Check each answer against correct option
    for question, selected_option in answers.items():
        cur.execute("SELECT answer FROM quizzes WHERE id=%s", (question,))
        correct_option = cur.fetchone()
        if correct_option and correct_option[0] == selected_option:
            score += 1

    # Optional: Store score in a quiz_scores table (if you have one)
    # Example:
    cur.execute("INSERT INTO quiz_scores (name, standard, subject, score, total) VALUES (%s, %s, %s, %s, %s)",
                (name, standard, subject, score, total_questions))
    con.commit()

    con.close()

    return render_template('student_result.html', name=name, score=score, total=total_questions, subject=subject)


@app.route('/quiz-scores')
def quiz_scores():
    if not session.get('teacher') and not session.get('admin'):
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM quiz_scores")
    scores = cur.fetchall()
    con.close()
    return render_template('quiz_scores.html', scores=scores)

@app.route('/upload', methods=['GET', 'POST'])
def upload_material():
    if not session.get('teacher'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        standard = request.form['standard']
        subject = request.form['subject']
        file = request.files['file']

        if file:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(upload_path)

            con = get_db_connection()
            cur = con.cursor()
            cur.execute("""
                INSERT INTO materials (title, standard, subject, filename)
                VALUES (%s, %s, %s, %s)
            """, (title, standard, subject, filename))
            con.commit()
            con.close()

            flash("Material uploaded successfully!")
            return redirect(url_for('teacher_dashboard'))

    return render_template('upload.html')

@app.route('/materials')
def view_materials():
    if not session.get('student'):
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()

    # Fetch student's standard using session username
    cur.execute("SELECT standard FROM users WHERE username=%s", (session['student'],))
    student_standard = cur.fetchone()[0]

    # Fetch study materials for that standard
    cur.execute("SELECT * FROM materials WHERE standard=%s", (student_standard,))
    materials = cur.fetchall()

    con.close()

    return render_template('materials.html', materials=materials)

@app.route('/edit-material/<int:id>', methods=['GET', 'POST'])
def edit_material(id):
    if 'teacher' not in session:
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()

    if request.method == 'POST':
        title = request.form['title']
        standard = request.form['standard']
        subject = request.form['subject']

        cur.execute("UPDATE materials SET title=%s, standard=%s, subject=%s WHERE id=%s",
                    (title, standard, subject, id))
        con.commit()
        con.close()
        flash("Material updated successfully.")
        return redirect(url_for('teacher_dashboard'))

    cur.execute("SELECT * FROM materials WHERE id=%s", (id,))
    material = cur.fetchone()
    con.close()
    return render_template("edit_material.html", material=material)

@app.route('/delete-material/<int:id>')
def delete_material(id):
    if 'teacher' not in session:
        return redirect(url_for('login'))

    con = get_db_connection()
    cur = con.cursor()

    cur.execute("SELECT filename FROM materials WHERE id=%s", (id,))
    file = cur.fetchone()
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file[0])
        if os.path.exists(filepath):
            os.remove(filepath)

    cur.execute("DELETE FROM materials WHERE id=%s", (id,))
    con.commit()
    con.close()
    flash("Material deleted.")
    return redirect(url_for('teacher_dashboard'))

@app.route('/student', methods=['GET', 'POST'])
def student_dashboard():
    if 'student' not in session:
        return redirect(url_for('login'))

    username = session['student']
    con = get_db_connection()
    cur = con.cursor()

    # Get student's own standard
    cur.execute("SELECT standard FROM users WHERE username=%s", (username,))
    result = cur.fetchone()

    if not result:
        flash("Could not fetch your standard.")
        return redirect(url_for('login'))

    student_standard = result[0]

    # Get available subjects for this student's standard
    cur.execute("SELECT DISTINCT subject FROM materials WHERE standard=%s", (student_standard,))
    subjects = [r[0] for r in cur.fetchall()]

    # Get messages for students
    cur.execute("SELECT content FROM messages WHERE recipient IN ('student', 'all')")
    messages = [row[0] for row in cur.fetchall()]

    # Get vote titles the student has voted in
    cur.execute("SELECT vote_title FROM student_votes WHERE username = %s", (username,))
    voted_titles = [row[0] for row in cur.fetchall()]

    materials = []

    if request.method == 'POST':
        selected_subject = request.form.get('subject')

        query = "SELECT * FROM materials WHERE standard = %s"
        params = [student_standard]

        if selected_subject:
            query += " AND subject = %s"
            params.append(selected_subject)

        cur.execute(query, params)
        materials = cur.fetchall()

    con.close()

    return render_template(
        "student_home.html",
        subjects=subjects,
        materials=materials,
        messages=messages,
        voted_titles=voted_titles,
        student_standard=student_standard
    )

# ------------------ Host Meeting ------------------
@app.route('/host-meeting')
def host_meeting():
    if 'teacher' not in session:
        return redirect(url_for('login'))
    room_name = "classroom_" + session['teacher']
    return render_template("live_meeting.html", room_name=room_name, user=session['teacher'], role='teacher')

# ------------------ Join Meeting ------------------
@app.route('/join-meeting')
def join_meeting():
    if 'student' not in session:
        return redirect(url_for('login'))
    room_name = "classroom_teacher"  # You can make this dynamic later
    return render_template("live_meeting.html", room_name=room_name, user=session['student'], role='student')

# ------------------ Submit Feedback ------------------
@app.route('/feedback', methods=['POST'])
def feedback():
    if 'student' not in session:
        return redirect(url_for('login'))
    name = request.form['name']
    rating = request.form['rating']
    comment = request.form['comment']
    con = get_db_connection()
    cursor = con.cursor()
    cursor.execute("INSERT INTO feedback (student_name, rating, comment) VALUES (%s, %s, %s)", (name, rating, comment))
    con.commit()
    con.close()
    flash("Thanks for your feedback!")
    return redirect(url_for('student_dashboard'))

# ------------------ View Feedback ------------------
@app.route('/view-feedback')
def view_feedback():
    if 'teacher' not in session:
        return redirect(url_for('login'))
    con = get_db_connection()
    cursor = con.cursor()
    cursor.execute("SELECT student_name, rating, comment FROM feedback")
    feedbacks = cursor.fetchall()
    con.close()
    return render_template("view_feedback.html", feedbacks=feedbacks)


if __name__ == '__main__':
    app.run(debug=True)
