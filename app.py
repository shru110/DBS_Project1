# ==========================================
# 1. IMPORTS
# ==========================================
import mysql.connector
import functools
import os
from flask import (
    Flask, request, redirect, url_for, 
    render_template, session, g, abort, flash
)
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

# ==========================================
# 2. CONFIGURATION & APP INITIALIZATION
# ==========================================
app = Flask(__name__)

# Mandatory for sessions and security
app.config['SECRET_KEY'] = 'a_very_long_and_complex_random_string_of_your_own_creation'

# Add this configuration for file uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'blend', 'fig', 'py', 'css'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database Credentials
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'Shru#110' # This is your password
DB_NAME = 'portfolio'

# Initialize libraries
bcrypt = Bcrypt(app)

# ==========================================
# 3. DATABASE CONNECTION & HELPER FUNCTIONS
# ==========================================
def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

# Helper function for file uploads
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# 4. SECURITY & AUTH DECORATORS
# ==========================================

@app.before_request
def load_logged_in_user():
    """Checks session for user_id and loads user data into 'g' object."""
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT user_id, first_name, last_name, email, role FROM user WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            g.user = cursor.fetchone()
            cursor.close()
            conn.close()
        else:
            g.user = None

def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# ==========================================
# 5. AUTHENTICATION ROUTES
# ==========================================

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form.get('last_name', '')
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'Standard')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            insert_query = """
                INSERT INTO user 
                (first_name, last_name, email, password_hash, role) 
                VALUES (%s, %s, %s, %s, %s) 
            """
            user_data = (first_name, last_name, email, hashed_password, role)
            
            try:
                cursor.execute(insert_query, user_data)
                conn.commit()
                return redirect(url_for('login'))
            except mysql.connector.Error as err:
                error = "Email already registered." if err.errno == 1062 else "Database Error."
                return render_template('signup.html', error=error)
            finally:
                cursor.close()
                conn.close()
    
    return render_template('signup.html') 

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email')
    password_attempt = request.form.get('password')

    if not email or not password_attempt:
        error = 'Please fill out all fields.'
        return render_template('login.html', error=error)

    user_record = None
    conn = get_db_connection()

    if conn is None:
        error = 'Server error: Could not connect to database.'
        return render_template('login.html', error=error)
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT user_id, password_hash FROM user WHERE email = %s"
        cursor.execute(query, (email,))
        user_record = cursor.fetchone() 
        
    except mysql.connector.Error as err:
        print(f"Login Query Error: {err}")
        error = 'A database error occurred during login.'
        return render_template('login.html', error=error)
    
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        conn.close()

    if user_record and bcrypt.check_password_hash(user_record['password_hash'], password_attempt):
        session.clear()
        session['user_id'] = user_record['user_id']
        return redirect(url_for('dashboard'))
    else:
        error = 'Invalid email or password.'

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 6. APPLICATION ROUTES
# ==========================================

@app.route('/')
def index():
    """Redirects root URL (/) to login page."""
    return redirect(url_for('login'))

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        start_date = request.form['start_date']
        completion_date = request.form.get('completion_date') or None
        client_id = request.form['client_id']
        
        # CORRECTED: Use dictionary access for g.user
        user_id = g.user['user_id'] 
        selected_skills = request.form.getlist('skills')
        selected_tags = request.form.getlist('tags')

        cursor = conn.cursor()

        try:
            project_insert_query = """
                INSERT INTO project (title, status, description, start_date, completion_date, client_id) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(project_insert_query, (title, status, description, start_date, completion_date, client_id))
            new_project_id = cursor.lastrowid

            cursor.execute("INSERT INTO project_user (project_id, user_id) VALUES (%s, %s)", (new_project_id, user_id))

            for skill_id in selected_skills:
                cursor.execute("INSERT INTO project_skill (project_id, skill_id) VALUES (%s, %s)", (new_project_id, skill_id))
            for tag_id in selected_tags:
                cursor.execute("INSERT INTO project_tag (project_id, tag_id) VALUES (%s, %s)", (new_project_id, tag_id))

            # --- Handle Asset Uploads ---
            if 'asset_files' in request.files:
                files = request.files.getlist('asset_files')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{new_project_id}_{filename}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                        
                        asset_query = """
                            INSERT INTO asset (project_id, file_name, file_type, storage_location, date_uploaded)
                            VALUES (%s, %s, %s, %s, CURDATE())
                        """
                        file_type = filename.rsplit('.', 1)[1].lower()
                        storage_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        cursor.execute(asset_query, (new_project_id, filename, file_type, storage_path))

            # --- Handle Initial Feedback ---
            feedback_rating = request.form.get('feedback_rating')
            feedback_comment = request.form.get('feedback_comment')
            if feedback_rating and feedback_comment:
                feedback_query = """
                    INSERT INTO feedback (project_id, user_id, rating, coment, date)
                    VALUES (%s, %s, %s, %s, CURDATE())
                """
                cursor.execute(feedback_query, (new_project_id, user_id, feedback_rating, feedback_comment))

            conn.commit()
            flash('Project added successfully!', 'success')
            return redirect(url_for('dashboard'))

        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Error adding project: {err}', 'danger')
            return redirect(url_for('add_project'))
        
        finally:
            cursor.close()
            conn.close()

    # --- THIS IS THE GET REQUEST PART ---
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT client_id, client_name FROM client")
        clients = cursor.fetchall()
        
        cursor.execute("SELECT skill_id, skill_name FROM skill")
        skills = cursor.fetchall()

        cursor.execute("SELECT tag_id, tag_name FROM tag")
        tags = cursor.fetchall()
        
        return render_template('add_project.html', clients=clients, skills=skills, tags=tags)
    
    except mysql.connector.Error as err:
        print(f"Error fetching form data: {err}")
        flash("Failed to load form data.", "danger")
        return redirect(url_for('dashboard'))
    
    finally:
        cursor.close()
        conn.close()

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for('projects_list'))
    
    cursor = conn.cursor(dictionary=True)

    # CORRECTED: Use dictionary access for g.user
    cursor.execute("SELECT project_id FROM project_user WHERE project_id = %s AND user_id = %s", (project_id, g.user['user_id']))
    if cursor.fetchone() is None:
        abort(403)

    cursor.execute("SELECT * FROM project WHERE project_id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        flash("Project not found.", "danger")
        return redirect(url_for('projects_list'))

    if request.method == 'POST':
        try:
            if 'asset_files' in request.files:
                files = request.files.getlist('asset_files')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{project_id}_{filename}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                        asset_query = """
                            INSERT INTO asset (project_id, file_name, file_type, storage_location, date_uploaded)
                            VALUES (%s, %s, %s, %s, CURDATE())
                        """
                        file_type = filename.rsplit('.', 1)[1].lower()
                        storage_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        cursor.execute(asset_query, (project_id, filename, file_type, storage_path))

            feedback_rating = request.form.get('feedback_rating')
            feedback_comment = request.form.get('feedback_comment')
            if feedback_rating and feedback_comment:
                feedback_query = """
                    INSERT INTO feedback (project_id, user_id, rating, coment, date)
                    VALUES (%s, %s, %s, %s, CURDATE())
                """
                # CORRECTED: Use dictionary access for g.user
                cursor.execute(feedback_query, (project_id, g.user['user_id'], feedback_rating, feedback_comment))
            
            new_completion_date = request.form.get('completion_date')
            if new_completion_date:
                cursor.execute("UPDATE project SET completion_date = %s WHERE project_id = %s", (new_completion_date, project_id))

            conn.commit()
            flash('Project updated successfully!', 'success')
            return redirect(url_for('edit_project', project_id=project_id))

        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Error updating project: {err}', 'danger')
        
        finally:
            cursor.close()
            conn.close()

    cursor.execute("SELECT * FROM asset WHERE project_id = %s ORDER BY date_uploaded DESC", (project_id,))
    assets = cursor.fetchall()
    cursor.execute("SELECT f.*, u.first_name FROM feedback f JOIN user u ON f.user_id = u.user_id WHERE f.project_id = %s ORDER BY f.date DESC", (project_id,))
    feedback = cursor.fetchall()
    cursor.execute("SELECT client_id, client_name FROM client")
    clients = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('edit_project.html', project=project, assets=assets, feedback=feedback, clients=clients)


@app.route('/dashboard')
@login_required 
def dashboard():
    dashboard_data = {} 
    
    conn = get_db_connection()
    if conn is None:
        return render_template('dashboard.html', error="Database connection failed.") 

    cursor = conn.cursor(dictionary=True)

    try:
        # CORRECTED: Use dictionary access for g.user
        cursor.execute("SELECT COUNT(*) AS total_projects FROM project p JOIN project_user pu ON p.project_id = pu.project_id WHERE pu.user_id = %s", (g.user['user_id'],))
        total_projects_result = cursor.fetchone()
        dashboard_data['total_projects_count'] = total_projects_result['total_projects']

        # CORRECTED: Use dictionary access for g.user
        cursor.execute("SELECT COUNT(*) AS completed_projects FROM project p JOIN project_user pu ON p.project_id = pu.project_id WHERE pu.user_id = %s AND p.status = 1", (g.user['user_id'],))
        completed_projects_result = cursor.fetchone()
        dashboard_data['completed_projects_count'] = completed_projects_result['completed_projects']

        # CORRECTED: All queries below now filter by current user and use g.user['user_id']
        
        q1_query = """
            SELECT c.client_name AS Client, c.industry AS Industry, SUM(p.total_hours_spent) AS Total_Hours_Across_Projects, COUNT(p.project_id) AS Number_of_Projects
            FROM client c INNER JOIN project p ON c.client_id = p.client_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s
            GROUP BY c.client_name, c.industry ORDER BY Total_Hours_Across_Projects DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q1_query, (g.user['user_id'],))
        dashboard_data['client_summary'] = cursor.fetchall()

        q3_query = """
            SELECT s.skill_name AS Skill, COUNT(ps.project_id) AS Projects_Used_In
            FROM skill s INNER JOIN project_skill ps ON s.skill_id = ps.skill_id
            INNER JOIN project_user pu ON ps.project_id = pu.project_id
            WHERE pu.user_id = %s
            GROUP BY s.skill_name HAVING COUNT(ps.project_id) > 0 ORDER BY Projects_Used_In DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q3_query, (g.user['user_id'],))
        dashboard_data['top_skills'] = cursor.fetchall()

        q5_query = """
            SELECT p.project_id, p.title AS Project_Title, COUNT(a.asset_id) AS Number_of_Assets, SUM(a.file_size_KB) AS Total_Size_KB
            FROM project p INNER JOIN asset a ON p.project_id = a.project_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE p.status = 0 AND pu.user_id = %s
            GROUP BY p.project_id, p.title
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q5_query, (g.user['user_id'],))
        dashboard_data['in_progress_assets'] = cursor.fetchall()

        q7_query = """
            SELECT s.skill_name AS Skill, AVG(ps.skill_proficiency_rating) AS Average_Proficiency_Rating
            FROM skill s INNER JOIN project_skill ps ON s.skill_id = ps.skill_id
            INNER JOIN project_user pu ON ps.project_id = pu.project_id
            WHERE pu.user_id = %s
            GROUP BY s.skill_name ORDER BY Average_Proficiency_Rating DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q7_query, (g.user['user_id'],))
        dashboard_data['skill_proficiency'] = cursor.fetchall()

        q8_query = """
            SELECT CONCAT(u.first_name, ' ', u.last_name) AS Reviewer, u.role AS Role, COUNT(f.feedback_id) AS Total_Feedback_Given
            FROM user u INNER JOIN feedback f ON u.user_id = f.user_id
            INNER JOIN project p ON f.project_id = p.project_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s
            GROUP BY u.user_id, Reviewer, u.role ORDER BY Total_Feedback_Given DESC LIMIT 1
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q8_query, (g.user['user_id'],))
        dashboard_data['top_reviewer'] = cursor.fetchone()

        q10_query = """
            SELECT p.project_id, p.title AS Project_Title, c.client_name AS Client_Name, p.completion_date, p.total_hours_spent AS Total_Effort_Hours
            FROM project p INNER JOIN client c ON p.client_id = c.client_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s AND p.total_hours_spent IS NOT NULL
            ORDER BY p.total_hours_spent DESC LIMIT 5
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q10_query, (g.user['user_id'],))
        dashboard_data['top_projects'] = cursor.fetchall()

        q11_query = """
            SELECT u.role AS Team_Role, SUM(tl.hours_worked) AS Total_Hours_Logged_By_Role
            FROM user u INNER JOIN time_log tl ON u.user_id = tl.user_id
            WHERE u.user_id = %s
            GROUP BY u.role ORDER BY Total_Hours_Logged_By_Role DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q11_query, (g.user['user_id'],))
        dashboard_data['role_workload'] = cursor.fetchall()

        q13_query = """
            SELECT a.file_type AS File_Extension, COUNT(a.asset_id) AS Count_of_Files, SUM(a.file_size_KB) AS Total_Size_KB
            FROM asset a INNER JOIN project p ON a.project_id = p.project_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s
            GROUP BY a.file_type ORDER BY Count_of_Files DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q13_query, (g.user['user_id'],))
        dashboard_data['file_types'] = cursor.fetchall()

        q15_query = """
            SELECT p.title AS Collaborative_Project, COUNT(pu.user_id) AS Number_of_Collaborators
            FROM project p INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE p.project_id IN (SELECT project_id FROM project_user WHERE user_id = %s)
            GROUP BY p.title HAVING COUNT(pu.user_id) > 1 ORDER BY Number_of_Collaborators DESC
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q15_query, (g.user['user_id'],))
        dashboard_data['collaborative_projects'] = cursor.fetchall()

        return render_template('dashboard.html', user=g.user, data=dashboard_data)

    except mysql.connector.Error as err:
        print(f"Database Query Error: {err}")
        return render_template('dashboard.html', error="Failed to load portfolio data due to database error.")
        
    finally:
        cursor.close()
        conn.close()

@app.route('/projects')
@login_required
def projects_list():
    industry_filter = request.args.get('industry', '')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    
    conn = get_db_connection()
    if conn is None:
        return render_template('projects.html', error="Database connection failed.")
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT p.project_id, p.title AS Project_Title, c.client_name AS Client_Name, c.industry,
                   p.start_date, p.completion_date, p.status, p.total_hours_spent
            FROM project p INNER JOIN client c ON p.client_id = c.client_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s
        """
        # CORRECTED: Use dictionary access for g.user
        params = [g.user['user_id']]
        
        if industry_filter:
            query += " AND c.industry = %s"
            params.append(industry_filter)
        
        if start_date_filter:
            query += " AND p.start_date >= %s"
            params.append(start_date_filter)
        
        if end_date_filter:
            query += " AND p.completion_date <= %s"
            params.append(end_date_filter)
        
        query += " ORDER BY p.start_date DESC"
        
        cursor.execute(query, tuple(params))
        projects = cursor.fetchall()
        
        cursor.execute("SELECT DISTINCT industry FROM client ORDER BY industry")
        industries = cursor.fetchall()
        
        return render_template('projects.html', 
                             projects=projects, 
                             industries=industries,
                             selected_industry=industry_filter)
    
    except mysql.connector.Error as err:
        print(f"Projects Query Error: {err}")
        return render_template('projects.html', error="Failed to load projects.")
    
    finally:
        cursor.close()
        conn.close()

@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    project_data = {}
    
    conn = get_db_connection()
    if conn is None: 
        return render_template('project_detail.html', error="Database connection error."), 500
    
    cursor = conn.cursor(dictionary=True)

    # CORRECTED: Use dictionary access for g.user
    cursor.execute("SELECT project_id FROM project_user WHERE project_id = %s AND user_id = %s", (project_id, g.user['user_id']))
    if cursor.fetchone() is None:
        abort(403)

    try:
        q2_query = """
            SELECT p.title AS Project_Title, CONCAT(u.first_name, ' ', u.last_name) AS Team_Member, SUM(tl.hours_worked) AS Total_Hours_Logged
            FROM project p INNER JOIN time_log tl ON p.project_id = tl.project_id
            INNER JOIN user u ON tl.user_id = u.user_id
            WHERE p.project_id = %s
            GROUP BY p.title, Team_Member
        """
        cursor.execute(q2_query, (project_id,))
        project_data['team_hours'] = cursor.fetchall()

        basic_query = """
            SELECT p.project_id, p.title, p.description, p.total_hours_spent, p.start_date, p.completion_date, p.status,
                   c.client_name, c.industry, c.contact_email
            FROM project p JOIN client c ON p.client_id = c.client_id
            WHERE p.project_id = %s
        """
        cursor.execute(basic_query, (project_id,))
        project_data['summary'] = cursor.fetchone()
        
        if not project_data['summary']:
            abort(404)
        
        assets_query = """
            SELECT file_name, file_type, file_size_KB, storage_location, date_uploaded 
            FROM asset WHERE project_id = %s ORDER BY date_uploaded DESC
        """
        cursor.execute(assets_query, (project_id,))
        project_data['assets'] = cursor.fetchall()

        feedback_query = """
            SELECT CONCAT(u.first_name, ' ', u.last_name) AS Reviewer_Name, f.rating, f.coment, f.date
            FROM feedback f INNER JOIN user u ON f.user_id = u.user_id
            WHERE f.project_id = %s ORDER BY f.date DESC
        """
        cursor.execute(feedback_query, (project_id,))
        project_data['feedback'] = cursor.fetchall()

        tags_query = """
            SELECT t.tag_name FROM project_tag pt JOIN tag t ON pt.tag_id = t.tag_id WHERE pt.project_id = %s
        """
        cursor.execute(tags_query, (project_id,))
        project_data['tags'] = cursor.fetchall()

        skills_query = """
            SELECT s.skill_name, ps.skill_proficiency_rating
            FROM project_skill ps JOIN skill s ON ps.skill_id = s.skill_id
            WHERE ps.project_id = %s ORDER BY ps.skill_proficiency_rating DESC
        """
        cursor.execute(skills_query, (project_id,))
        project_data['skills'] = cursor.fetchall()

        team_query = """
            SELECT CONCAT(u.first_name, ' ', u.last_name) AS name, u.role, u.email
            FROM project_user pu JOIN user u ON pu.user_id = u.user_id
            WHERE pu.project_id = %s
        """
        cursor.execute(team_query, (project_id,))
        project_data['team'] = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Project Detail Query Error: {err}")
        return render_template('project_detail.html', error="Failed to load project details.")
        
    finally:
        cursor.close()
        conn.close()

    return render_template('project_detail.html', project=project_data)

@app.route('/analytics')
@login_required
def analytics():
    analytics_data = {}
    
    conn = get_db_connection()
    if conn is None:
        return render_template('analytics.html', error="Database connection failed.")
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        q4_query = """
            SELECT DISTINCT p.project_id, p.title AS Project_Title, p.completion_date
            FROM project p INNER JOIN project_skill ps ON p.project_id = ps.project_id
            INNER JOIN skill s ON ps.skill_id = s.skill_id AND s.skill_name = 'Python'
            INNER JOIN project_tag pt ON p.project_id = pt.project_id
            INNER JOIN tag t ON pt.tag_id = t.tag_id AND t.tag_name = 'Data Analysis'
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q4_query, (g.user['user_id'],))
        analytics_data['python_data_projects'] = cursor.fetchall()

        q9_query = """
            SELECT p.project_id, p.title AS Project_Title, p.start_date, p.description
            FROM project p LEFT JOIN asset a ON p.project_id = a.project_id
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            WHERE pu.user_id = %s AND a.asset_id IS NULL
        """
        # CORRECTED: Use dictionary access for g.user
        cursor.execute(q9_query, (g.user['user_id'],))
        analytics_data['projects_without_assets'] = cursor.fetchall()
        
        return render_template('analytics.html', data=analytics_data)
    
    except mysql.connector.Error as err:
        print(f"Analytics Query Error: {err}")
        return render_template('analytics.html', error="Failed to load analytics.")
    
    finally:
        cursor.close()
        conn.close()

# ==========================================
# 7. RUN APPLICATION
# ==========================================
if __name__ == '__main__':
    app.run(debug=True)