from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from firebase import initialize_firebase, verify_google_id_token, get_empresa_by_correo, create_empresa, update_empresa, get_vacantes_by_empresa_id, create_vacante

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
    # Redirect to empresa_datos which handles all the logic
    return redirect(url_for('empresa_datos'))

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

    correo = session['user_email']

    # Handle POST request (form submission to update data)
    if request.method == 'POST':
        # Get the empresa document ID from session
        doc_id = session.get('empresa_doc_id')

        if not doc_id:
            flash('Error: No se encontró el documento de la empresa.', 'error')
            return redirect(url_for('empresa_datos'))

        # Collect form data (only update non-None values)
        update_data = {}

        fields = ['nombre', 'contactoPrincipal', 'estado', 'giro', 'mun_alcaldia']
        for field in fields:
            value = request.form.get(field, '').strip()
            if value:  # Only include non-empty values
                update_data[field] = value

        if update_data:
            # Update the empresa document
            if update_empresa(doc_id, update_data):
                flash('Datos de la empresa actualizados exitosamente.', 'success')
                # Refresh the page to show updated data
                return redirect(url_for('empresa_datos'))
            else:
                flash('Error al actualizar los datos. Inténtalo de nuevo.', 'error')
        else:
            flash('No se proporcionaron datos para actualizar.', 'info')

    # GET request: Check if empresa exists in Firestore
    empresa = get_empresa_by_correo(correo)

    if empresa:
        # Empresa exists, store doc_id in session
        session['empresa_doc_id'] = empresa['doc_id']
        is_new_empresa = False
    else:
        # Empresa doesn't exist, create new document
        doc_id = create_empresa(correo)
        if doc_id:
            session['empresa_doc_id'] = doc_id
            # Fetch the newly created empresa
            empresa = get_empresa_by_correo(correo)
            is_new_empresa = True
            flash('Bienvenido! Por favor completa los datos de tu empresa.', 'info')
        else:
            flash('Error al crear el registro de la empresa.', 'error')
            return redirect(url_for('empresas_login'))

    # Prepare data for template
    empresa_data = {
        "nombre": empresa.get('nombre'),
        "contacto_principal": empresa.get('contactoPrincipal'),
        "correo": empresa.get('correo'),
        "giro": empresa.get('giro'),
        "estado": empresa.get('estado'),
        "municipio": empresa.get('mun_alcaldia'),
        "suscripcion_activa": empresa.get('suscripcionActiva', False),
        "is_new": is_new_empresa,
        "doc_id": empresa.get('doc_id')  # Include doc_id for API KEY display
    }

    return render_template('empresa_datos.html', empresa=empresa_data)

@app.route('/empresa/dashboard')
def empresa_dashboard():
    # Check if user is authenticated as empresa
    if 'user_email' not in session or session.get('user_role') != 'empresa':
        return redirect(url_for('empresas_login'))

    # Get empresa document ID from session
    doc_id = session.get('empresa_doc_id')

    if not doc_id:
        # If doc_id is not in session, fetch it from Firestore
        correo = session['user_email']
        empresa = get_empresa_by_correo(correo)

        if empresa:
            doc_id = empresa['doc_id']
            session['empresa_doc_id'] = doc_id
        else:
            flash('Error: No se encontró la empresa. Por favor completa tus datos primero.', 'error')
            return redirect(url_for('empresa_datos'))

    # Get all vacantes for this empresa
    vacantes = get_vacantes_by_empresa_id(doc_id)

    return render_template('empresa_dashboard.html', vacantes=vacantes)

@app.route('/empresas/nueva-vacante', methods=['GET', 'POST'])
def nueva_vacante():
    # Check if user is authenticated as empresa
    if 'user_email' not in session or session.get('user_role') != 'empresa':
        return redirect(url_for('empresas_login'))

    # Get empresa document ID from session
    doc_id = session.get('empresa_doc_id')

    if not doc_id:
        # If doc_id is not in session, fetch it from Firestore
        correo = session['user_email']
        empresa = get_empresa_by_correo(correo)

        if empresa:
            doc_id = empresa['doc_id']
            session['empresa_doc_id'] = doc_id
        else:
            flash('Error: No se encontró la empresa. Por favor completa tus datos primero.', 'error')
            return redirect(url_for('empresa_datos'))

    # Get empresa data for the form
    empresa = get_empresa_by_correo(session['user_email'])

    if request.method == 'POST':
        # Collect form data
        vacante_data = {
            'titulo': request.form.get('titulo', '').strip(),
            'descripcion': request.form.get('descripcion', '').strip(),
            'requisitos': request.form.get('requisitos', '').strip(),
            'modalidad': request.form.get('modalidad', '').strip(),
            'tipoContrato': request.form.get('tipoContrato', '').strip(),
            'duracion': request.form.get('duracion', '').strip(),
            'horario': request.form.get('horario', '').strip(),
            'educacion': request.form.get('educacion', '').strip(),
            'experienciaRequerida': request.form.get('experienciaRequerida', '').strip(),
            'nombreEmpresa': empresa.get('nombre', '')
        }

        # Handle sueldo (number)
        sueldo_str = request.form.get('sueldo', '').strip()
        if sueldo_str:
            try:
                vacante_data['sueldo'] = float(sueldo_str)
            except ValueError:
                vacante_data['sueldo'] = None
        else:
            vacante_data['sueldo'] = None

        # Handle arrays: habilidadesDuras and idiomas
        habilidades_str = request.form.get('habilidadesDuras', '').strip()
        if habilidades_str:
            vacante_data['habilidadesDuras'] = [h.strip() for h in habilidades_str.split(',') if h.strip()]
        else:
            vacante_data['habilidadesDuras'] = []

        idiomas_str = request.form.get('idiomas', '').strip()
        if idiomas_str:
            vacante_data['idiomas'] = [i.strip() for i in idiomas_str.split(',') if i.strip()]
        else:
            vacante_data['idiomas'] = []

        # Validate required fields
        if not vacante_data['titulo']:
            flash('El título de la vacante es obligatorio.', 'error')
        else:
            # Create the vacante
            vacante_id = create_vacante(doc_id, vacante_data)

            if vacante_id:
                flash('Vacante creada exitosamente.', 'success')
                return redirect(url_for('empresa_dashboard'))
            else:
                flash('Error al crear la vacante. Inténtalo de nuevo.', 'error')

    return render_template('nueva_vacante.html', empresa=empresa)

if __name__ == '__main__':
    app.run(debug=True)