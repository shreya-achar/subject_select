import uuid, os, hashlib, pymysql, datetime
from flask import Flask, request, render_template, redirect, url_for, session, abort, flash, jsonify
app = Flask(__name__)

# Register the setup page and import create_connection()
from utils import create_connection, setup
app.register_blueprint(setup)

# Don't let any user access a page without logging in
@app.before_request
def restrict():
    restricted_pages = [
        'list_users',
        'view_user',
        'edit_user',
        'delete_user',
        'subjects_list',
        'selected_subjects',
        'add_subject',
        'delete_subject',

        ]
    if 'logged_in' not in session and request.endpoint in restricted_pages:
        flash("You are not logged in.")
        return redirect('/login')

@app.route('/')
def home():
    return render_template("index.html")

# Let the user login in with their email and password
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        password = request.form['password']
        encrypted_password = hashlib.sha256(password.encode()).hexdigest()

        with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = """SELECT * FROM users WHERE email = %s AND password = %s"""
                values = (
                    request.form['email'],
                    encrypted_password
                )
                cursor.execute(sql, values)
                result = cursor.fetchone()

            if result:
                session['logged_in'] = True
                session['first_name'] = result['first_name']
                session['user_id'] = result['user_id']
                session['role'] = result['role']
                if session['role'] == 'admin':
                    return redirect('/dashboard')
                else:
                    return redirect (url_for('view_user', user_id=session['user_id']))                    
            else:
                flash("Invalid username or password.")
                return redirect('/login')
    else:
        return render_template("login.html")

# Logout the user and return to the home page 
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Let the user register their details
@app.route('/register', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':

        password = request.form['password']
        encrypted_password = hashlib.sha256(password.encode()).hexdigest()

        if request.files['avatar'].filename:
            avatar_image = request.files["avatar"]
            ext = os.path.splitext(avatar_image.filename)[1]
            avatar_filename = str(uuid.uuid4())[:8] + ext
            avatar_image.save("static/images/" + avatar_filename)
        else:
            avatar_filename = None

        with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = """INSERT INTO users 
                    (first_name, last_name, email, password, avatar)
                    VALUES (%s, %s, %s, %s, %s)"""
                values = (
                    request.form['first_name'],
                    request.form['last_name'],
                    request.form['email'],
                    encrypted_password,
                    avatar_filename
                )
                cursor.execute(sql, values)
                connection.commit()

# Login in the user after they sign up and take them to their profile page
                sql = """SELECT * FROM users WHERE email = %s AND password = %s"""
                values = (
                    request.form['email'],
                    encrypted_password
                )
                cursor.execute(sql, values)
                result = cursor.fetchone()

            if result:
                session['logged_in'] = True
                session['first_name'] = result['first_name']
                session['role'] = result['role']
                session['user_id'] = result['user_id']
                return redirect (url_for('view_user', user_id=session['user_id']))

    return render_template('users_add.html')

# Show the admin a list of the users 
@app.route('/dashboard')
def list_users():
    #Only the admin is allowed to view the dashboard
    if session['role'] != 'admin':
        flash("You don't have permission to view this page.")
        return redirect (url_for('view_user', user_id=session['user_id']))
    with create_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
    return render_template('users_list.html', result=result)

# Show the user a list of subjects
@app.route('/subjects')
def subjects_list():
    with create_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM subjects")
            result = cursor.fetchall()
    return render_template('subjects_list.html', result=result)

#Show the user their profile with their details
@app.route('/view')
def view_user():
    #Only admins and the user is allowed to view their profile, everyone else is redirected to their profile
    if session['role'] != 'admin' and str(session['user_id']) != request.args['user_id']:
        flash("You don't have permission to view this page.")
        return redirect (url_for('view_user', user_id=session['user_id']))
    with create_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT * FROM users WHERE user_id = %s""", request.args['user_id'])
            result = cursor.fetchone()
    return render_template('users_view.html', result=result)

# Show the user their selected subjects
@app.route('/selected')
def selected_subjects():
    #Only  the admin and the user is allowed to view their subject list
    if session['role'] != 'admin' and str(session['user_id']) != request.args['user_id']:
        flash("You don't have permission to view this page.")
        return redirect (url_for('view_user', user_id=session['user_id']))
    with create_connection() as connection:
        with connection.cursor() as cursor:
            sql = """SELECT * FROM users
                        JOIN student_subjects ON student_subjects.user_id = users.user_id
                        JOIN subjects ON subjects.subject_id = student_subjects.subject_id 
                        WHERE users.user_id = %s"""
            values = (
                request.args['user_id']
                )
            cursor.execute(sql, values)
            result = cursor.fetchall()            
            sql = """SELECT * FROM users
                        WHERE users.user_id = %s"""
            values = (
                request.args['user_id']
                )
            cursor.execute(sql, values)
            student = cursor.fetchone()
    return render_template('selected_list.html', result=result, student=student)
 
# Show the admin the students of a subject
@app.route('/viewsub')
def view_subjects():
    with create_connection() as connection:
        with connection.cursor() as cursor:
            sql = """SELECT * FROM users
                        JOIN student_subjects ON student_subjects.user_id = users.user_id
                        JOIN subjects ON subjects.subject_id = student_subjects.subject_id 
                        WHERE subjects.subject_id = %s;"""
            values = (
                request.args['subject_id']
                )
            cursor.execute(sql, values)
            result = cursor.fetchall()
            sql = """SELECT * FROM subjects
                     WHERE subjects.subject_id = %s"""
            values = (
                request.args['subject_id']
                )
            cursor.execute(sql, values)
            subject = cursor.fetchone()
    return render_template('subjects_view.html', result=result, subject=subject)

# Let the user add a subject to their subjects selected list
@app.route('/addsub')
def add_subject():

    # Set the startdate and enddate for subject selection
    today = datetime.date.today()
    startdate = datetime.date(2022, 7, 11)
    enddate = datetime.date(2022, 7, 12)

    with create_connection() as connection:
        with connection.cursor() as cursor:
            if today < startdate:
                flash("You can't select subjects until " + str(startdate))
                return redirect ('/subjects') 
            elif today > enddate:
                flash("Subject selection ended on " + str(enddate))
                return redirect ('/subjects') 
            else:
                sql = """SELECT subject_id FROM student_subjects
                         WHERE student_subjects.user_id = %s"""
                values = (
                    session['user_id']
                )
                cursor.execute(sql, values)
                subject_list = cursor.fetchall()
                # Don't let the user any more than 5 subjects
                [i['subject_id'] for i in subject_list]
                count = int (len(subject_list))
                if count < 5:
                    sql = """INSERT INTO student_subjects 
                            (user_id, subject_id) 
                            VALUES (%s, %s)"""
                    values = (
                        session['user_id'],
                        request.args['subject_id']
                    )
                    try:
                        cursor.execute(sql, values)
                        connection.commit()
                    except pymysql.err.IntegrityError:
                            flash("You've already chosen that subject")
                            return redirect('/subjects')
                else:
                    flash("You've already chosen 5 subjects")
                    return redirect('/subjects')
    return redirect ('/selected?user_id=' + str(session['user_id'])) 

# Let the user delete a subject off their subject selected list
@app.route('/deletesub')
def delete_subject():
    with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = "DELETE FROM student_subjects WHERE subject_id=%s"
                values = (
                    request.args['subject_id']
                    )
                cursor.execute(sql, values)
                connection.commit()
    return redirect ('/selected?user_id=' + str(session['user_id']))

# Let the admin delete the user
@app.route('/delete')
def delete_user():
    #Only the admin is allowed to delete a user
    if session['role'] != 'admin':
        flash("You don't have permission to delete this user.")
        return redirect (url_for('view_user', user_id=session['user_id']))
    with create_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE user_id=%s", request.args['user_id'])
                connection.commit()
    return render_template ('users_list.html')

#Let the user edit their details 
@app.route('/edit', methods=['GET', 'POST'])
def edit_user():
    #Only the admin and the user is allowed to edit their profile
    if session['role'] != 'admin' and str(session['user_id']) != request.args['user_id']:
        flash("You don't have permission to edit that user.")
        return redirect (url_for('view_user', user_id=session['user_id']))
    if request.method == 'POST':
        if request.files['avatar'].filename:
            avatar_image = request.files["avatar"]
            ext = os.path.splitext(avatar_image.filename)[1]
            avatar_filename = str(uuid.uuid4())[:8] + ext
            avatar_image.save("static/images/" + avatar_filename)
            if request.form['old_avatar'] != 'None':
                os.remove("static/images/" + request.form['old_avatar'])
        elif request.form['old_avatar'] != 'None':
            avatar_filename = request.form['old_avatar']
        else:
            avatar_filename = None

        with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = """UPDATE users SET
                    first_name = %s,
                    last_name = %s,
                    email = %s,
                    avatar = %s
                WHERE user_id = %s"""
                values = (
                    request.form['first_name'],
                    request.form['last_name'],
                    request.form['email'],
                    avatar_filename,
                    request.form['user_id']
                )
                cursor.execute(sql, values)
                connection.commit()
        return redirect('/view?user_id=' + request.form['user_id'])
    else:
        with create_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE user_id = %s", request.args['user_id'])
                result = cursor.fetchone()
        return render_template('users_edit.html', result=result)

# Let the admin add a subject 
@app.route('/adminaddsub', methods=['GET', 'POST'])
def adminadd_subject():
    if request.method == 'POST':
        with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = "INSERT INTO subjects (subject_name) VALUES (%s)"
                values = (
                    request.form['subject_name']
                    )
                cursor.execute(sql, values)
                connection.commit()
                return redirect('/subjects')
    return render_template('subj_add.html')

# Let the admin edit a subject 
@app.route('/admineditsub', methods=['GET', 'POST'])
def adminedit_subject():
    if request.method == 'POST':
        with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = "UPDATE subjects SET subject_name = %s WHERE subject_id = %s"
                values = (
                          request.form['subject_name'],
                          request.form['subject_id']
                          )
                cursor.execute(sql, values)
                connection.commit()
        return redirect('/subjects')
    else:
        with create_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", request.args['subject_id'])
                result = cursor.fetchone()
        return render_template('subj_edit.html', result=result)

# Let the admin delete a subject
@app.route('/admindeletesub')
def admindelete_subject():
    with create_connection() as connection:
            with connection.cursor() as cursor:
                sql = "DELETE FROM subjects WHERE subject_id=%s"
                values = (
                    request.args['subject_id']
                    )
                cursor.execute(sql, values)
                connection.commit()
    return redirect ('/subjects')

# Check the email when signing up 
@app.route('/checkemail')
def check_email():
    with create_connection() as connection:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM users WHERE email = %s"
            values = (
                request.args['email']
            )
            cursor.execute(sql, values)
            result = cursor.fetchone()
    if result:
        return jsonify({ 'status': 'Error' })
    else:
        return jsonify({ 'status': 'OK' })

if __name__ == '__main__':
    import os

    # This is required to allow flashing messages.
    app.secret_key = os.urandom(32)

    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    app.run(HOST, PORT, debug=True)