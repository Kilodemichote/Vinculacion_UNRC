from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from firebase import initialize_firebase, verify_google_id_token

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')

# Initialize Firebase Admin SDK
initialize_firebase()

# Secret key for session management - change this in production
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

@app.route('/')
def index():
    return redirect('/home')

@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/alumnos')
def alumnos():
    # Redirect to login if not authenticated
    return redirect(url_for('alumnos_login'))

@app.route('/alumnos/login', methods=['GET', 'POST'])
def alumnos_login():
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        
        # Validate form data
        errors, clean_email, clean_password = validate_login_form(email, password)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('alumnos_login.html')
        
        # Attempt authentication
        user = authenticate_user_firebase(clean_email, clean_password)
        
        if user:
            # Successful login
            session['user_id'] = user['user_id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            
            # Clear failed attempts
            auth_manager.clear_failed_attempts(clean_email)
            
            flash(f'¡Bienvenido, {user["name"]}!', 'success')
            return redirect(url_for('alumnos_dashboard'))
        else:
            # Failed login
            auth_manager.record_failed_attempt(clean_email)
            flash('Credenciales incorrectas. Verifica tu email y contraseña.', 'error')
    
    return render_template('alumnos_login.html')

@app.route('/alumnos/register', methods=['GET', 'POST'])
def alumnos_register():
    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate form data
        errors, clean_email, clean_password = validate_register_form(email, password, confirm_password)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('alumnos_register.html')
        
        # Attempt user creation
        try:
            user = create_user_firebase(clean_email, clean_password)
            if user:
                flash('Cuenta creada exitosamente. Ya puedes iniciar sesión.', 'success')
                return redirect(url_for('alumnos_login'))
        except Exception as e:
            flash('Error al crear la cuenta. El email podría estar en uso.', 'error')
    
    return render_template('alumnos_register.html')

@app.route('/alumnos/forgot-password', methods=['GET', 'POST'])
def alumnos_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '')
        clean_email = auth_manager.sanitize_input(email)
        
        if not clean_email:
            flash('El campo de email es obligatorio', 'error')
        elif not auth_manager.validate_email(clean_email):
            flash('Por favor, ingresa un email válido', 'error')
        else:
            # Generate reset token
            reset_token = auth_manager.generate_reset_token(clean_email)
            
            # Send reset email (implement actual email sending)
            if send_password_reset_email(clean_email, reset_token):
                flash('Se ha enviado un enlace de recuperación a tu email.', 'info')
                return redirect(url_for('alumnos_login'))
            else:
                flash('Error al enviar el email. Inténtalo más tarde.', 'error')
    
    return render_template('alumnos_forgot_password.html')

@app.route('/alumnos/dashboard')
def alumnos_dashboard():
    return render_template('alumnos_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('home'))

@app.route('/empresas')
def empresas():
    # Redirect to login if not authenticated as a company
    if 'user_role' not in session or session['user_role'] != 'empresa':
        return redirect(url_for('empresas_login'))
    return render_template('empresa_datos.html') # A new dashboard for companies

@app.route('/empresas/login', methods=['GET', 'POST'])
def empresas_login():
    # Prepare Firebase config for the client-side
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
    }

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        # NOTE: This is a placeholder for company authentication.
        # You would replace this with your actual company user validation logic.
        # For now, we only handle Google Sign-In for companies.
        flash('El inicio de sesión con email y contraseña para empresas no está habilitado. Por favor, usa Google.', 'info')
    return render_template('empresas_login.html', firebase_config=firebase_config)

# Replace the empresas_google_login function
@app.route('/empresas/google-login', methods=['POST'])
def empresas_google_login():
    data = request.get_json()
    id_token = data.get('idToken')

    if not id_token:
        return jsonify({"success": False, "error": "No ID token provided."}), 400

    user_info = verify_google_id_token(id_token)

    if user_info:
        session['user_id'] = user_info['uid']
        session['user_email'] = user_info['email']
        session['user_name'] = user_info.get('name', user_info['email'])
        session['user_role'] = 'empresa'
        
        # Redirect to empresa_datos for upsert
        return jsonify({"success": True, "redirectUrl": url_for('empresa_datos')})
    else:
        return jsonify({"success": False, "error": "Invalid ID token."}), 401

# Add new endpoint for empresa_datos
@app.route('/empresa_datos', methods=['GET', 'POST'])
def empresa_datos():
    if 'user_email' not in session:
        return redirect(url_for('empresas_login'))
    
    # Upsert email to Firestore
    from firebase import upsert_empresa_email
    upsert_empresa_email(session['user_email'])
    
    # Render a form or dashboard (create this template)
    return render_template('empresa_datos.html')

if __name__ == '__main__':
    app.run(debug=True)