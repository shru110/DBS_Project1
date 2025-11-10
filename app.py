# ==========================================
# 1. IMPORTS
# ==========================================
import mysql.connector
import functools
from flask import (
    Flask, request, redirect, url_for, 
    render_template, session, g, abort, flash
)
from flask_bcrypt import Bcrypt

# ==========================================
# 2. CONFIGURATION & APP INITIALIZATION
# ==========================================
app = Flask(__name__)  # Corrected: was Flask(name)

# Mandatory for sessions and security
app.config['SECRET_KEY'] = 'a_very_long_and_complex_random_string_of_your_own_creation'

# Database Credentials for portfolio6
DB_HOST = '127.0.0.1'
DB_USER = 'root'
DB_PASSWORD = 'ved_0906'
DB_NAME = 'portfolio6'

# Initialize libraries
bcrypt = Bcrypt(app)

# ==========================================
# 3. DATABASE CONNECTION FUNCTION
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

# ==========================================
# NEW ROUTE FOR ADDING PROJECTS
# ==========================================

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    """
    Handles the creation of a new project.
    GET: Displays the form.
    POST: Processes the form data and inserts into the database.
    """
    conn = get_db_connection()
    if conn is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Get form data
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        start_date = request.form['start_date']
        completion_date = request.form.get('completion_date') or None # Handle empty date
        client_id = request.form['client_id']
        
        # Get current user ID from session
        user_id = session['user_id']

        # Get multi-select data for skills and tags
        selected_skills = request.form.getlist('skills')
        selected_tags = request.form.getlist('tags')

        cursor = conn.cursor()

        try:
            # 1. Insert the main project record
            project_insert_query = """
                INSERT INTO project (title, status, description, start_date, completion_date, client_id) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            project_data = (title, status, description, start_date, completion_date, client_id)
            cursor.execute(project_insert_query, project_data)
            
            # Get the ID of the newly created project
            new_project_id = cursor.lastrowid

            # 2. Link the current user to the new project
            project_user_insert_query = "INSERT INTO project_user (project_id, user_id) VALUES (%s, %s)"
            cursor.execute(project_user_insert_query, (new_project_id, user_id))

            # 3. Link selected skills to the project
            for skill_id in selected_skills:
                project_skill_insert_query = "INSERT INTO project_skill (project_id, skill_id) VALUES (%s, %s)"
                cursor.execute(project_skill_insert_query, (new_project_id, skill_id))
            
            # 4. Link selected tags to the project
            for tag_id in selected_tags:
                project_tag_insert_query = "INSERT INTO project_tag (project_id, tag_id) VALUES (%s, %s)"
                cursor.execute(project_tag_insert_query, (new_project_id, tag_id))

            # Commit all changes to the database
            conn.commit()
            flash('Project added successfully!', 'success')
            return redirect(url_for('dashboard'))

        except mysql.connector.Error as err:
            # If something goes wrong, rollback any changes
            conn.rollback()
            flash(f'Error adding project: {err}', 'danger')
            print(f"Database Error: {err}") # For debugging
            return redirect(url_for('add_project'))
        
        finally:
            cursor.close()
            conn.close()

    # For GET request: fetch data to populate the form dropdowns
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

@app.route('/dashboard')
@login_required 
def dashboard():
    """
    Dashboard displaying portfolio analytics using queries from your SQL file.
    Based on Q1, Q3, Q5, Q7, Q8, Q10, Q11, Q13, Q15 from your original queries.
    """
    dashboard_data = {} 
    
    conn = get_db_connection()
    if conn is None:
        return render_template('dashboard.html', error="Database connection failed.") 

    cursor = conn.cursor(dictionary=True)

    try:
        # Q1: Client Project Effort Summary
        q1_query = """
            SELECT
                c.client_name AS Client,
                c.industry AS Industry,
                SUM(p.total_hours_spent) AS Total_Hours_Across_Projects,
                COUNT(p.project_id) AS Number_of_Projects
            FROM client c
            INNER JOIN project p ON c.client_id = p.client_id
            GROUP BY c.client_name, c.industry
            ORDER BY Total_Hours_Across_Projects DESC
        """
        cursor.execute(q1_query)
        dashboard_data['client_summary'] = cursor.fetchall()

        # Q3: Portfolio Skill Demand (Skills used in MORE THAN ONE project)
        q3_query = """
            SELECT
                s.skill_name AS Skill,
                COUNT(ps.project_id) AS Projects_Used_In
            FROM skill s
            INNER JOIN project_skill ps ON s.skill_id = ps.skill_id
            GROUP BY s.skill_name
            HAVING COUNT(ps.project_id) > 1
            ORDER BY Projects_Used_In DESC
        """
        cursor.execute(q3_query)
        dashboard_data['top_skills'] = cursor.fetchall()

        # Q5: Asset Stats for In-Progress Projects
        q5_query = """
            SELECT
                p.project_id,  -- Added project_id
                p.title AS Project_Title,
                COUNT(a.asset_id) AS Number_of_Assets,
                SUM(a.file_size_KB) AS Total_Size_KB
            FROM project p
            INNER JOIN asset a ON p.project_id = a.project_id
            WHERE p.status = 0
            GROUP BY p.project_id, p.title
        """
        cursor.execute(q5_query)
        dashboard_data['in_progress_assets'] = cursor.fetchall()

        # Q7: Average Proficiency per Skill
        q7_query = """
            SELECT
                s.skill_name AS Skill,
                AVG(ps.skill_proficiency_rating) AS Average_Proficiency_Rating
            FROM skill s
            INNER JOIN project_skill ps ON s.skill_id = ps.skill_id
            GROUP BY s.skill_name
            ORDER BY Average_Proficiency_Rating DESC
        """
        cursor.execute(q7_query)
        dashboard_data['skill_proficiency'] = cursor.fetchall()

        # Q8: Most Active Reviewer
        q8_query = """
            SELECT
                CONCAT(u.first_name, ' ', u.last_name) AS Reviewer,
                u.role AS Role,
                COUNT(f.feedback_id) AS Total_Feedback_Given
            FROM user u
            INNER JOIN feedback f ON u.user_id = f.user_id
            GROUP BY u.user_id, Reviewer, u.role
            ORDER BY Total_Feedback_Given DESC
            LIMIT 1
        """
        cursor.execute(q8_query)
        dashboard_data['top_reviewer'] = cursor.fetchone()

        # Q10: Projects by Effort (Highest Hours Spent)
        q10_query = """
            SELECT
                p.project_id,  -- Added project_id
                p.title AS Project_Title,
                c.client_name AS Client_Name,
                p.completion_date,
                p.total_hours_spent AS Total_Effort_Hours
            FROM project p
            INNER JOIN client c ON p.client_id = c.client_id
            WHERE p.total_hours_spent IS NOT NULL
            ORDER BY p.total_hours_spent DESC
            LIMIT 5
        """
        cursor.execute(q10_query)
        dashboard_data['top_projects'] = cursor.fetchall()

        # Q11: User Workload by Role
        q11_query = """
            SELECT
                u.role AS Team_Role,
                SUM(tl.hours_worked) AS Total_Hours_Logged_By_Role
            FROM user u
            INNER JOIN time_log tl ON u.user_id = tl.user_id
            GROUP BY u.role
            ORDER BY Total_Hours_Logged_By_Role DESC
        """
        cursor.execute(q11_query)
        dashboard_data['role_workload'] = cursor.fetchall()

        # Q13: Asset File Type Distribution
        q13_query = """
            SELECT
                a.file_type AS File_Extension,
                COUNT(a.asset_id) AS Count_of_Files,
                SUM(a.file_size_KB) AS Total_Size_KB
            FROM asset a
            GROUP BY a.file_type
            ORDER BY Count_of_Files DESC
        """
        cursor.execute(q13_query)
        dashboard_data['file_types'] = cursor.fetchall()

        # Q15: Collaborative Project Identification
        q15_query = """
            SELECT
                p.title AS Collaborative_Project,
                COUNT(pu.user_id) AS Number_of_Collaborators
            FROM project p
            INNER JOIN project_user pu ON p.project_id = pu.project_id
            GROUP BY p.title
            HAVING COUNT(pu.user_id) > 1
            ORDER BY Number_of_Collaborators DESC
        """
        cursor.execute(q15_query)
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
    """
    Display all projects with filtering options.
    Based on Q12 and Q14 from your SQL queries.
    """
    # Get filter parameters
    industry_filter = request.args.get('industry', '')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    
    conn = get_db_connection()
    if conn is None:
        return render_template('projects.html', error="Database connection failed.")
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Base query
        query = """
            SELECT
                p.project_id,  -- Added project_id
                p.title AS Project_Title,
                c.client_name AS Client_Name,
                c.industry,
                p.start_date,
                p.completion_date,
                p.status,
                p.total_hours_spent
            FROM project p
            INNER JOIN client c ON p.client_id = c.client_id
            WHERE 1=1
        """
        params = []
        
        # Add filters dynamically
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
        
        # Get list of industries for filter dropdown
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
    """
    Display detailed information about a specific project.
    Based on Q2, Q6, Q9 from your SQL queries.
    """
    project_data = {}
    
    conn = get_db_connection()
    if conn is None: 
        return render_template('project_detail.html', error="Database connection error."), 500
    
    cursor = conn.cursor(dictionary=True)

    try:
        # Q2: Team Workload on Specific Project
        q2_query = """
            SELECT
                p.title AS Project_Title,
                CONCAT(u.first_name, ' ', u.last_name) AS Team_Member,
                SUM(tl.hours_worked) AS Total_Hours_Logged
            FROM project p
            INNER JOIN time_log tl ON p.project_id = tl.project_id
            INNER JOIN user u ON tl.user_id = u.user_id
            WHERE p.project_id = %s
            GROUP BY p.title, Team_Member
        """
        cursor.execute(q2_query, (project_id,))
        project_data['team_hours'] = cursor.fetchall()

        # Project Basic Info
        basic_query = """
            SELECT 
                p.project_id,  -- Added project_id
                p.title, 
                p.description, 
                p.total_hours_spent, 
                p.start_date,
                p.completion_date,
                p.status,
                c.client_name, 
                c.industry,
                c.contact_email
            FROM project p 
            JOIN client c ON p.client_id = c.client_id
            WHERE p.project_id = %s
        """
        cursor.execute(basic_query, (project_id,))
        project_data['summary'] = cursor.fetchone()
        
        if not project_data['summary']:
            abort(404)
        
        # Assets for this project
        assets_query = """
            SELECT 
                file_name, 
                file_type, 
                file_size_KB, 
                storage_location,
                date_uploaded 
            FROM asset 
            WHERE project_id = %s 
            ORDER BY date_uploaded DESC
        """
        cursor.execute(assets_query, (project_id,))
        project_data['assets'] = cursor.fetchall()

        # Feedback for this project (Q6: Top Rated Feedback)
        feedback_query = """
            SELECT
                CONCAT(u.first_name, ' ', u.last_name) AS Reviewer_Name,
                f.rating,
                f.coment,
                f.date
            FROM feedback f
            INNER JOIN user u ON f.user_id = u.user_id
            WHERE f.project_id = %s
            ORDER BY f.date DESC
        """
        cursor.execute(feedback_query, (project_id,))
        project_data['feedback'] = cursor.fetchall()

        # Tags for this project
        tags_query = """
            SELECT t.tag_name
            FROM project_tag pt
            JOIN tag t ON pt.tag_id = t.tag_id
            WHERE pt.project_id = %s
        """
        cursor.execute(tags_query, (project_id,))
        project_data['tags'] = cursor.fetchall()

        # Skills used in this project
        skills_query = """
            SELECT 
                s.skill_name,
                ps.skill_proficiency_rating
            FROM project_skill ps
            JOIN skill s ON ps.skill_id = s.skill_id
            WHERE ps.project_id = %s
            ORDER BY ps.skill_proficiency_rating DESC
        """
        cursor.execute(skills_query, (project_id,))
        project_data['skills'] = cursor.fetchall()

        # Team members on this project
        team_query = """
            SELECT 
                CONCAT(u.first_name, ' ', u.last_name) AS name,
                u.role,
                u.email
            FROM project_user pu
            JOIN user u ON pu.user_id = u.user_id
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
    """
    Analytics page showing Q4 and Q9 queries.
    """
    analytics_data = {}
    
    conn = get_db_connection()
    if conn is None:
        return render_template('analytics.html', error="Database connection failed.")
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Q4: Complex Tag Filter (Projects using Python AND Data Analysis)
        q4_query = """
            SELECT DISTINCT
                p.project_id,  -- Added project_id
                p.title AS Project_Title,
                p.completion_date
            FROM project p
            INNER JOIN project_skill ps ON p.project_id = ps.project_id
            INNER JOIN skill s ON ps.skill_id = s.skill_id AND s.skill_name = 'Python'
            INNER JOIN project_tag pt ON p.project_id = pt.project_id
            INNER JOIN tag t ON pt.tag_id = t.tag_id AND t.tag_name = 'Data Analysis'
        """
        cursor.execute(q4_query)
        analytics_data['python_data_projects'] = cursor.fetchall()

        # Q9: Projects Missing Assets
        q9_query = """
            SELECT
                p.project_id,  -- Added project_id
                p.title AS Project_Title,
                p.start_date,
                p.description
            FROM project p
            LEFT JOIN asset a ON p.project_id = a.project_id
            WHERE a.asset_id IS NULL
        """
        cursor.execute(q9_query)
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
if __name__ == '__main__':  # Corrected: was _name_ and _main_
    app.run(debug=True)