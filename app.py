from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from backend.auth import (
    validate_login_form, 
    validate_register_form,
    authenticate_user_firebase,
    create_user_firebase,
    send_password_reset_email,
    auth_manager,
    login_required
)
import os

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')

# Secret key for session management - change this in production
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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
@login_required
def alumnos_dashboard():
    return render_template('alumnos_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('home'))

@app.route('/empresas')
def empresas():
    # Route for companies access
    return render_template('empresas.html')

if __name__ == '__main__':
    app.run(debug=True)