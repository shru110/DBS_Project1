# ==========================================
# 1. IMPORTS
# ==========================================
import mysql.connector
import functools # For the login_required decorator
from flask import (
    Flask, request, redirect, url_for, 
    render_template, session, g, abort
)
from flask_bcrypt import Bcrypt

# ==========================================
# 2. CONFIGURATION & APP INITIALIZATION
# ==========================================
app = Flask(__name__)

# Mandatory for sessions and security
app.config['SECRET_KEY'] = 'a_very_long_and_complex_random_string_of_your_own_creation'

# Database Credentials
DB_HOST = '127.0.0.1'
DB_USER = 'root'
DB_PASSWORD = 'ved_0906' # Your specific password
DB_NAME = 'portfolio2_updated'

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

# A. Before Request Hook (Runs before every page load)
@app.before_request
def load_logged_in_user():
    """Checks session for user_id and loads user data into the 'g' object."""
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT user_id, first_name, email FROM user WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            g.user = cursor.fetchone()
            cursor.close()
            conn.close()
        else:
            g.user = None

# B. Login Required Decorator
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

# NOTE: For the sign-up route to work, you MUST set user_id to AUTO_INCREMENT 
# in your CREATE TABLE user DDL, otherwise you need robust ID generation code.

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        email = request.form['email']
        password = request.form['password']
        
        # 1. Input Validation and Email Check (Missing, but necessary)
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Use NULL for user_id if you set it to AUTO_INCREMENT
            insert_query = """
                INSERT INTO user 
                (user_id, first_name, email, password_hash, role) 
                VALUES (NULL, %s, %s, %s, %s) 
            """
            user_data = (first_name, email, hashed_password, 'Standard') # Note: user_id removed from tuple
            
            try:
                cursor.execute(insert_query, user_data)
                conn.commit()
                return redirect(url_for('login'))
            except mysql.connector.Error as err:
                 # Handle duplicate email error (Error 1062 in MySQL)
                error = "Email already registered." if err.errno == 1062 else "Database Error."
                return render_template('signup.html', error=error)
            finally:
                cursor.close()
                conn.close()
    
    return render_template('signup.html') 


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    # Renders the login form on GET request or if there's an error on POST
    if request.method == 'GET':
        return render_template('login.html')

    # --- POST REQUEST HANDLING (Login Attempt) ---

    email = request.form.get('email')
    password_attempt = request.form.get('password')

    # Initial quick check for empty fields (good practice)
    if not email or not password_attempt:
        error = 'Please fill out all fields.'
        return render_template('login.html', error=error)

    # 1. Database Retrieval Block
    user_record = None
    conn = get_db_connection()

    if conn is None:
        # If the database is completely unreachable
        error = 'Server error: Could not connect to the database.'
        return render_template('login.html', error=error)
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Retrieve Hash: Secure parameterized query
        query = "SELECT user_id, password_hash FROM user WHERE email = %s"
        cursor.execute(query, (email,))
        user_record = cursor.fetchone() 
        
    except mysql.connector.Error as err:
        # Handle query execution errors (e.g., table not found)
        print(f"Login Query Error: {err}")
        error = 'A database error occurred during login.'
        return render_template('login.html', error=error)
    
    finally:
        # Crucial: Ensure resources are closed
        if 'cursor' in locals() and cursor:
            cursor.close()
        conn.close()

    # 2. Verification Logic (No database interaction needed here)
    if user_record and bcrypt.check_password_hash(user_record['password_hash'], password_attempt):
        
        # SUCCESS: Create Session and Redirect
        session.clear()
        session['user_id'] = user_record['user_id']
        # Use g.user['first_name'] here if you want a welcome message later
        # session['user_name'] = user_record['first_name'] 
        
        return redirect(url_for('dashboard'))
    else:
        # FAILURE: Password mismatch or Email not found (Keep message generic for security)
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
    """Redirects the root URL (/) to the login page."""
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required 
def dashboard():
    user_id = g.user['user_id']
    # 1. Initialize data dictionary
    dashboard_data = {} 
    
    # 2. Establish Connection
    conn = get_db_connection()
    if conn is None:
        return render_template('dashboard.html', error="Database connection failed.") 

    cursor = conn.cursor(dictionary=True)

    try:
 # --- EXECUTION BLOCK FOR TYPE 2 QUERIES (Q6, Q7, Q8, Q9, Q10, Q14) ---
        # 1. Q6: User's Owned Projects List
        q6_query = """
            SELECT project_id, title, CASE status WHEN 1 THEN 'Completed' ELSE 'In Progress' END AS status_text
            FROM project WHERE owner_user_id = %s ORDER BY start_date DESC;
        """
        cursor.execute(q6_query, (user_id,))
        dashboard_data['projects'] = cursor.fetchall()

        # 2. Q7: Overall Time Spent by Client
        q7_query = """
            SELECT c.client_name, SUM(p.total_hours_spent) AS total_hours_logged 
            FROM project p JOIN client c ON p.client_id = c.client_id WHERE p.owner_user_id = %s GROUP BY c.client_name 
            ORDER BY total_hours_logged DESC;
        """
        cursor.execute(q7_query, (user_id,))
        dashboard_data['client_hours'] = cursor.fetchall()

        # 3. Q8: Total Assets and Storage Used (Metrics)
        q8_query = """
         SELECT COUNT(a.asset_id) AS total_assets, SUM(a.file_size_KB) AS total_size_KB
         FROM project p INNER JOIN asset a ON p.project_id = a.project_id WHERE p.owner_user_id = %s;
        """
        cursor.execute(q8_query, (user_id,))
        dashboard_data['asset_stats'] = cursor.fetchone() 

        # 4. Q9: Top 3 Most Used Skills
        q9_query = """
            SELECT s.skill_name AS skill, COUNT(ps.project_id) AS projects_used_in
            FROM project p INNER JOIN project_skill ps ON p.project_id = ps.skill_id
            INNER JOIN skill s ON ps.skill_id = s.skill_id
            WHERE p.owner_user_id = %s GROUP BY s.skill_name ORDER BY projects_used_in DESC LIMIT 3;
        """
        cursor.execute(q9_query, (user_id,))
        dashboard_data['top_skills'] = cursor.fetchall()
        
        # 5. Q10: Average Project Rating
        q10_query = """
            SELECT AVG(f.rating) AS average_rating
            FROM project p INNER JOIN feedback f ON p.project_id = f.project_id
            WHERE p.owner_user_id = %s;
        """
        cursor.execute(q10_query, (user_id,))
        avg_rating_result = cursor.fetchone()
        
        if avg_rating_result and avg_rating_result['average_rating'] is not None:
            dashboard_data['avg_rating'] = round(avg_rating_result['average_rating'], 2)
        else:
         dashboard_data['avg_rating'] = 'N/A'

        # 6. Q14: Project Count by Industry
        q14_query = """
            SELECT c.industry, COUNT(p.project_id) AS number_of_projects
            FROM project p INNER JOIN client c ON p.client_id = c.client_id
            WHERE p.owner_user_id = %s GROUP BY c.industry ORDER BY number_of_projects DESC;
        """
        cursor.execute(q14_query, (user_id,))
        dashboard_data['industry_breakdown'] = cursor.fetchall()
        
        # --- END OF EXECUTION BLOCK ---

        # 4. Final Render
        return render_template('dashboard.html', user=g.user, data=dashboard_data)

    except mysql.connector.Error as err:
        print(f"Database Query Error: {err}")
        return render_template('dashboard.html', error="Failed to load portfolio data due to database error.")
        
    finally:
        # 5. Cleanup (Ensures connection closes regardless of success or failure)
        cursor.close()
        conn.close()


@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    """
    Handles the detail view for a specific project, fetching Q1-Q5 data 
    and enforcing authorization.
    """
    user_id = g.user['user_id']
    project_data = {}
    
    conn = get_db_connection()
    if conn is None: 
        return render_template('project_detail.html', error="Database connection error."), 500
    
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. AUTHORIZATION CHECK (Security Critical!)
        auth_query = "SELECT owner_user_id FROM project WHERE project_id = %s"
        cursor.execute(auth_query, (project_id,))
        owner_record = cursor.fetchone()
        
        # Deny access if project doesn't exist OR user is NOT the owner.
        if owner_record is None or owner_record['owner_user_id'] != user_id:
            cursor.close()
            conn.close()
            abort(403) 

        # --- 2. DATA RETRIEVAL (TYPE 1 QUERIES Q1-Q5) ---

        # Q1: Project Summary and Client Details (Single Fetch)
        q1_query = """
            SELECT 
                p.title, p.description, p.total_hours_spent, p.completion_date,
                c.client_name, c.industry
            FROM project p JOIN client c ON p.client_id = c.client_id
            WHERE p.project_id = %s;
        """
        cursor.execute(q1_query, (project_id,))
        project_data['summary'] = cursor.fetchone()

        # Q2: Team Hours Logged on Project (Multi Fetch)
        q2_query = """
            SELECT 
                CONCAT(u.first_name, ' ', u.last_name) AS team_member, 
                u.role,
                SUM(tl.hours_worked) AS total_hours_logged
            FROM time_log tl 
            JOIN user u ON tl.user_id = u.user_id
            WHERE tl.project_id = %s 
            GROUP BY team_member, u.role
            ORDER BY total_hours_logged DESC;
        """
        cursor.execute(q2_query, (project_id,))
        project_data['team_hours'] = cursor.fetchall()
        
        # Q3: Assets Stored for Project (Multi Fetch)
        q3_query = "SELECT file_name, file_type, file_size_KB, date_uploaded FROM asset WHERE project_id = %s ORDER BY date_uploaded DESC;"
        cursor.execute(q3_query, (project_id,))
        project_data['assets'] = cursor.fetchall()

        # Q4: Feedback Received for Project (Multi Fetch)
        q4_query = """
            SELECT CONCAT(u.first_name, ' ', u.last_name) AS reviewer, f.rating, f.coment, f.date
            FROM feedback f JOIN user u ON f.user_id = u.user_id
            WHERE f.project_id = %s ORDER BY f.date DESC;
        """
        cursor.execute(q4_query, (project_id,))
        project_data['feedback'] = cursor.fetchall()

        # Q5: Project Tags and Skills Used (Requires UNION - Two Parameters)
        q5_query = """
            SELECT 'Tag' AS Type, tag_name AS Name, NULL AS Proficiency
            FROM project_tag pt JOIN tag t ON pt.tag_id = t.tag_id WHERE pt.project_id = %s
            UNION ALL
            SELECT 'Skill' AS Type, s.skill_name AS Name, ps.skill_proficiency_rating AS Proficiency
            FROM project_skill ps JOIN skill s ON ps.skill_id = s.skill_id WHERE ps.project_id = %s;
        """
        # Note: UNION requires passing the project_id parameter twice.
        cursor.execute(q5_query, (project_id, project_id)) 
        project_data['tags_skills'] = cursor.fetchall()


    except mysql.connector.Error as err:
        print(f"Project Detail Query Error: {err}")
        return render_template('project_detail.html', error="Failed to load project details.")
        
    finally:
        # 3. Cleanup: Always close resources
        cursor.close()
        conn.close()

    # 4. Render Template
    return render_template('project_detail.html', project=project_data)

# This code is ready for the frontend integration right?