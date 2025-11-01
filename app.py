from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from firebase import (
    initialize_firebase,
    verify_google_id_token,
    get_empresa_by_correo,
    create_empresa,
    update_empresa,
    get_vacantes_by_empresa_id,
    create_vacante,
    get_empresa_by_id,
    update_vacante,
    delete_vacante,
    verify_vacante_belongs_to_empresa,
    get_all_empresas,
    update_empresa_subscription,
    get_alumno_by_correo,
    create_alumno,
    update_alumno,
)

app = Flask(
    __name__, template_folder="frontend/templates", static_folder="frontend/static"
)

# Disable template and static file caching for development
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Enable CORS for API endpoints (production ready)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize Firebase Admin SDK
initialize_firebase()

# Secret key for session management - change this in production
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")


@app.route("/")
def index():
    return redirect("/home")


@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/alumnos")
def alumnos():
    # Redirect to login if not authenticated
    return redirect(url_for("alumnos_login"))


@app.route("/alumnos/login", methods=["GET", "POST"])
def alumnos_login():
    # Prepare Firebase config for the client-side
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
    }

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        # NOTE: This is a placeholder for company authentication.
        # You would replace this with your actual company user validation logic.
        # For now, we only handle Google Sign-In for companies.
        flash(
            "El inicio de sesión con email y contraseña para empresas no está habilitado. Por favor, usa Google.",
            "info",
        )
    return render_template("alumnos_login.html", firebase_config=firebase_config)


# Replace the empresas_google_login function
# Endpoint de Google Login para Alumnos
@app.route("/alumnos/google-login", methods=["POST"])
def alumnos_google_login():  # <--- Nombre de función ÚNICO
    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "error": "No ID token provided."}), 400

    user_info = verify_google_id_token(id_token)

    if user_info:
        # Aquí deberías manejar la sesión/cookie para el alumno y redirigir
        # Por ahora, solo devolveremos una URL de prueba para que el JS funcione
        session["user_id"] = user_info["uid"]
        session["user_email"] = user_info["email"]
        session["user_role"] = "alumno"
        session["user_name"] = user_info.get("name", "Alumno")
        return jsonify({"success": True, "redirectUrl": url_for("alumnos_dashboard")})
    else:
        return jsonify({"success": False, "error": "Invalid ID token."}), 401

    return render_template("alumnos_login.html")


@app.route("/alumnos/register", methods=["GET", "POST"])
def alumnos_register():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate form data
        errors, clean_email, clean_password = validate_register_form(
            email, password, confirm_password
        )

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("alumnos_register.html")

        # Attempt user creation
        try:
            user = create_user_firebase(clean_email, clean_password)
            if user:
                flash(
                    "Cuenta creada exitosamente. Ya puedes iniciar sesión.", "success"
                )
                return redirect(url_for("alumnos_login"))
        except Exception as e:
            flash("Error al crear la cuenta. El email podría estar en uso.", "error")

    return render_template("alumnos_register.html")


@app.route("/alumnos/forgot-password", methods=["GET", "POST"])
def alumnos_forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "")
        clean_email = auth_manager.sanitize_input(email)

        if not clean_email:
            flash("El campo de email es obligatorio", "error")
        elif not auth_manager.validate_email(clean_email):
            flash("Por favor, ingresa un email válido", "error")
        else:
            # Generate reset token
            reset_token = auth_manager.generate_reset_token(clean_email)

            # Send reset email (implement actual email sending)
            if send_password_reset_email(clean_email, reset_token):
                flash("Se ha enviado un enlace de recuperación a tu email.", "info")
                return redirect(url_for("alumnos_login"))
            else:
                flash("Error al enviar el email. Inténtalo más tarde.", "error")

    return render_template("alumnos_forgot_password.html")


@app.route("/alumnos/dashboard")
def alumnos_dashboard():
    # 1. Proteger la ruta para que solo accedan alumnos
    if "user_role" not in session or session.get("user_role") != "alumno":
        flash("Acceso denegado. Por favor, inicia sesión como alumno.", "error")
        return redirect(url_for("alumnos_login"))

    # 2. Obtener el correo de la sesión
    correo_sesion = session.get("user_email")

    # 3. Buscar los datos del alumno en Firestore
    alumno_data = get_alumno_by_correo(correo_sesion)

    # 4. Renderizar la plantilla pasando los datos del alumno
    return render_template("alumnos_dashboard.html", alumno=alumno_data)


@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("home"))


@app.route("/alumnos/perfil", methods=["GET", "POST"])
def alumnos_perfil():
    # Verificar sesión
    if "user_email" not in session:
        return redirect(url_for("alumnos_login"))
    correo_sesion = session["user_email"]

    # POST: actualizar perfil
    if request.method == "POST":
        campos = [
            "nombre",
            "edad",
            "estatus",
            "semestre",
            "promedio",
            "area1",
            "area2",
            "area3",
            "habilidades_tecnicas",
            "habilidades_blandas",
            "idiomas",
        ]

        update_data = {}
        for campo in campos:
            valor = request.form.get(campo, "").strip()
            if valor:
                update_data[campo] = valor

        # Conversión de tipos
        for campo, tipo in [("edad", int), ("promedio", float)]:
            if campo in update_data:
                try:
                    update_data[campo] = tipo(update_data[campo])
                except ValueError:
                    flash(f"El campo {campo} debe ser un número.", "error")
                    return redirect(url_for("alumnos_perfil"))

        if not update_data:
            flash("No se proporcionaron datos nuevos para actualizar.", "info")
            return redirect(url_for("alumnos_perfil"))

        # Verificar si el alumno ya existe para decidir si crear o actualizar
        alumno_existente = get_alumno_by_correo(correo_sesion)

        if alumno_existente:
            # Actualizar perfil existente
            doc_id = alumno_existente["doc_id"]
            if update_alumno(doc_id, update_data):
                flash("Perfil actualizado exitosamente.", "success")
            else:
                flash("Error al actualizar el perfil. Inténtalo de nuevo.", "error")
        else:
            # Crear nuevo perfil con los datos del formulario
            update_data["correo"] = correo_sesion  # Añadir correo al nuevo documento
            if create_alumno(correo_sesion, update_data):
                flash("Perfil creado exitosamente.", "success")
            else:
                flash("Error al crear el perfil. Inténtalo de nuevo.", "error")

        return redirect(url_for("alumnos_dashboard"))

 # GET: mostrar perfil
    alumno_data = get_alumno_by_correo(correo_sesion)
    if alumno_data:
        is_new_alumno = False
    else:
        # No creamos el perfil aquí, solo preparamos para el formulario
        alumno_data = {}
        is_new_alumno = True
        flash(
            "¡Bienvenido! Por favor, completa tu perfil para que las empresas puedan conocerte.",
            "info",
        )

    if not alumno_data:
        alumno_data = {}  # Evita el error de NoneType

    alumno_render_data = {
        key: alumno_data.get(key)
        for key in [
            "nombre",
            "edad",
            "estatus",
            "semestre",
            "promedio",
            "area1",
            "area2",
            "area3",
            "habilidades_tecnicas",
            "habilidades_blandas",
            "idiomas",
        ]
    }

    alumno_render_data["is_new"] = is_new_alumno
    alumno_render_data["doc_id"] = alumno_data.get("doc_id")

    return render_template("alumnos_perfil.html", alumno=alumno_render_data)
@app.route('/alumnos/vacantes')
def alumnos_vacantes():
    # Prepara la configuración de Firebase para el lado del cliente
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
    }
    # Obtener datos del alumno si ha iniciado sesión
    alumno_logueado = None
    if session.get('user_role') == 'alumno' and 'user_email' in session:
        alumno_logueado = get_alumno_by_correo(session['user_email'])

    return render_template('alumnos_vacantes.html', firebase_config=firebase_config, alumno=alumno_logueado)

# 🔹 (Opcional) Ruta para recibir postulaciones desde el formulario
@app.route('/alumnos/postular', methods=['POST'])
def alumnos_postular():
    data = request.get_json()
    nombre = data.get('nombre')
    correo = data.get('correo')
    mensaje = data.get('mensaje')
    vacante_id = data.get('vacanteId')

    # Aquí podrías conectar con Firebase o guardar en tu base de datos
    print(f"Postulación recibida: {nombre} ({correo}) a la vacante {vacante_id}")
    
    return jsonify({"success": True, "msg": "Postulación recibida correctamente."})


# Empieza la seccion de empresas
@app.route("/empresas")
def empresas():
    # Redirect to login if not authenticated as a company
    if "user_role" not in session or session["user_role"] != "empresa":
        return redirect(url_for("empresas_login"))
    # Redirect to empresa_datos which handles all the logic
    return redirect(url_for("empresa_datos"))


@app.route("/empresas/login", methods=["GET", "POST"])
def empresas_login():
    # Prepare Firebase config for the client-side
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
    }

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        # Check for admin login
        admin_pwd = os.getenv("ADMIN_PWD")
        if email == "admin" and admin_pwd and password == admin_pwd:
            session["user_role"] = "admin"
            session["user_email"] = "admin"
            session["user_name"] = "Administrador"
            return redirect(url_for("admin_dashboard"))

        # If not admin, show message for regular empresa users
        flash(
            "El inicio de sesión con email y contraseña para empresas no está habilitado por el momento. Por favor, usa login de Google.",
            "info",
        )

    # Add cache-busting timestamp
    import time

    cache_bust = int(time.time())

    print(f"DEBUG: Rendering empresas_login with cache_bust={cache_bust}")

    return render_template(
        "empresas_login.html", firebase_config=firebase_config, cache_bust=cache_bust
    )


# Replace the empresas_google_login function
@app.route("/empresas/google-login", methods=["POST"])
def empresas_google_login():
    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "error": "No ID token provided."}), 400

    user_info = verify_google_id_token(id_token)

    if user_info:
        session["user_id"] = user_info["uid"]
        session["user_email"] = user_info["email"]
        session["user_name"] = user_info.get("name", user_info["email"])
        session["user_role"] = "empresa"

        # Redirect to empresa_datos for upsert
        return jsonify({"success": True, "redirectUrl": url_for("empresa_datos")})
    else:
        return jsonify({"success": False, "error": "Invalid ID token."}), 401


# Facebook login endpoint for empresas
@app.route("/empresas/facebook-login", methods=["POST"])
def empresas_facebook_login():
    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "error": "No ID token provided."}), 400

    user_info = verify_google_id_token(
        id_token
    )  # Firebase SDK verifies all provider tokens

    if user_info:
        session["user_id"] = user_info["uid"]
        session["user_email"] = user_info["email"]
        session["user_name"] = user_info.get("name", user_info["email"])
        session["user_role"] = "empresa"

        # Redirect to empresa_datos for upsert
        return jsonify({"success": True, "redirectUrl": url_for("empresa_datos")})
    else:
        return jsonify({"success": False, "error": "Invalid ID token."}), 401


# Add new endpoint for empresa_datos
@app.route("/empresa_datos", methods=["GET", "POST"])
def empresa_datos():
    if "user_email" not in session:
        return redirect(url_for("empresas_login"))

    correo = session["user_email"]

    # Handle POST request (form submission to update data)
    if request.method == "POST":
        # Get the empresa document ID from session
        doc_id = session.get("empresa_doc_id")

        if not doc_id:
            flash("Error: No se encontró el documento de la empresa.", "error")
            return redirect(url_for("empresa_datos"))

        # Collect form data (only update non-None values)
        update_data = {}

        fields = ["nombre", "contactoPrincipal", "estado", "giro", "mun_alcaldia"]
        for field in fields:
            value = request.form.get(field, "").strip()
            if value:  # Only include non-empty values
                update_data[field] = value

        if update_data:
            # Update the empresa document
            if update_empresa(doc_id, update_data):
                flash("Datos de la empresa actualizados exitosamente.", "success")
                # Refresh the page to show updated data
                return redirect(url_for("empresa_datos"))
            else:
                flash("Error al actualizar los datos. Inténtalo de nuevo.", "error")
        else:
            flash("No se proporcionaron datos para actualizar.", "info")

    # GET request: Check if empresa exists in Firestore
    empresa = get_empresa_by_correo(correo)

    if empresa:
        # Empresa exists, store doc_id in session
        session["empresa_doc_id"] = empresa["doc_id"]
        is_new_empresa = False
    else:
        # Empresa doesn't exist, create new document
        doc_id = create_empresa(correo)
        if doc_id:
            session["empresa_doc_id"] = doc_id
            # Fetch the newly created empresa
            empresa = get_empresa_by_correo(correo)
            is_new_empresa = True
            flash("Bienvenido! Por favor completa los datos de tu empresa.", "info")
        else:
            flash("Error al crear el registro de la empresa.", "error")
            return redirect(url_for("empresas_login"))

    # Prepare data for template
    empresa_data = {
        "nombre": empresa.get("nombre"),
        "contacto_principal": empresa.get("contactoPrincipal"),
        "correo": empresa.get("correo"),
        "giro": empresa.get("giro"),
        "estado": empresa.get("estado"),
        "municipio": empresa.get("mun_alcaldia"),
        "suscripcion_activa": empresa.get("suscripcionActiva", False),
        "is_new": is_new_empresa,
        "doc_id": empresa.get("doc_id"),  # Include doc_id for API KEY display
    }

    return render_template("empresa_datos.html", empresa=empresa_data)


@app.route("/empresa/dashboard")
def empresa_dashboard():
    # Check if user is authenticated as empresa
    if "user_email" not in session or session.get("user_role") != "empresa":
        return redirect(url_for("empresas_login"))

    # Get empresa document ID from session
    doc_id = session.get("empresa_doc_id")

    if not doc_id:
        # If doc_id is not in session, fetch it from Firestore
        correo = session["user_email"]
        empresa = get_empresa_by_correo(correo)

        if empresa:
            doc_id = empresa["doc_id"]
            session["empresa_doc_id"] = doc_id
        else:
            flash(
                "Error: No se encontró la empresa. Por favor completa tus datos primero.",
                "error",
            )
            return redirect(url_for("empresa_datos"))

    # Get all vacantes for this empresa
    vacantes = get_vacantes_by_empresa_id(doc_id)

    return render_template("empresa_dashboard.html", vacantes=vacantes)


@app.route("/admin/dashboard")
def admin_dashboard():
    # Check if user is authenticated as admin
    if "user_role" not in session or session.get("user_role") != "admin":
        flash("Acceso denegado. Solo administradores pueden acceder.", "error")
        return redirect(url_for("empresas_login"))

    # Get all empresas from Firebase
    empresas = get_all_empresas()

    return render_template("empresas_admin.html", empresas=empresas)


@app.route("/admin/update-subscription", methods=["POST"])
def admin_update_subscription():
    # Check if user is authenticated as admin
    if "user_role" not in session or session.get("user_role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    doc_id = data.get("doc_id")
    suscripcion_activa = data.get("suscripcionActiva")

    if not doc_id or suscripcion_activa is None:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    # Update the subscription status
    if update_empresa_subscription(doc_id, suscripcion_activa):
        return (
            jsonify({"success": True, "message": "Subscription updated successfully"}),
            200,
        )
    else:
        return (
            jsonify({"success": False, "error": "Failed to update subscription"}),
            500,
        )


@app.route("/empresas/nueva-vacante", methods=["GET", "POST"])
def nueva_vacante():
    # Check if user is authenticated as empresa
    if "user_email" not in session or session.get("user_role") != "empresa":
        return redirect(url_for("empresas_login"))

    # Get empresa document ID from session
    doc_id = session.get("empresa_doc_id")

    if not doc_id:
        # If doc_id is not in session, fetch it from Firestore
        correo = session["user_email"]
        empresa = get_empresa_by_correo(correo)

        if empresa:
            doc_id = empresa["doc_id"]
            session["empresa_doc_id"] = doc_id
        else:
            flash(
                "Error: No se encontró la empresa. Por favor completa tus datos primero.",
                "error",
            )
            return redirect(url_for("empresa_datos"))

    # Get empresa data for the form
    empresa = get_empresa_by_correo(session["user_email"])

    if request.method == "POST":
        # Collect form data
        vacante_data = {
            "titulo": request.form.get("titulo", "").strip(),
            "descripcion": request.form.get("descripcion", "").strip(),
            "requisitos": request.form.get("requisitos", "").strip(),
            "modalidad": request.form.get("modalidad", "").strip(),
            "tipoContrato": request.form.get("tipoContrato", "").strip(),
            "duracion": request.form.get("duracion", "").strip(),
            "horario": request.form.get("horario", "").strip(),
            "educacion": request.form.get("educacion", "").strip(),
            "experienciaRequerida": request.form.get(
                "experienciaRequerida", ""
            ).strip(),
            "nombreEmpresa": empresa.get("nombre", ""),
        }

        # Handle sueldo (number)
        sueldo_str = request.form.get("sueldo", "").strip()
        if sueldo_str:
            try:
                vacante_data["sueldo"] = float(sueldo_str)
            except ValueError:
                vacante_data["sueldo"] = None
        else:
            vacante_data["sueldo"] = None

        # Handle arrays: habilidadesDuras and idiomas
        habilidades_str = request.form.get("habilidadesDuras", "").strip()
        if habilidades_str:
            vacante_data["habilidadesDuras"] = [
                h.strip() for h in habilidades_str.split(",") if h.strip()
            ]
        else:
            vacante_data["habilidadesDuras"] = []

        idiomas_str = request.form.get("idiomas", "").strip()
        if idiomas_str:
            vacante_data["idiomas"] = [
                i.strip() for i in idiomas_str.split(",") if i.strip()
            ]
        else:
            vacante_data["idiomas"] = []

        # Validate required fields
        if not vacante_data["titulo"]:
            flash("El título de la vacante es obligatorio.", "error")
        else:
            # Create the vacante
            vacante_id = create_vacante(doc_id, vacante_data)

            if vacante_id:
                flash("Vacante creada exitosamente.", "success")
                return redirect(url_for("empresa_dashboard"))
            else:
                flash("Error al crear la vacante. Inténtalo de nuevo.", "error")

    return render_template("nueva_vacante.html", empresa=empresa)


# ==================== REST API ENDPOINTS ====================

from functools import wraps


def require_api_key(f):
    """
    Decorator to verify API key and empresa subscription status.
    The API key should be the empresa document ID and must be sent in the API_KEY header.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try multiple possible API key header names (case-insensitive)
        api_key = (
            request.headers.get("X-API-Key")
            or request.headers.get("X-Api-Key")
            or request.headers.get("API_KEY")
            or request.headers.get("Api-Key")
            or request.headers.get("api-key")
            or request.headers.get("apikey")
        )

        content_type = request.headers.get("Content-Type")

        # Verify Content-Type is application/json
        if content_type != "application/json":
            return (
                jsonify(
                    {"success": False, "error": "Content-Type must be application/json"}
                ),
                415,
            )

        # Verify API key is provided
        if not api_key:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "X-API-Key header is required (also accepts API_KEY, Api-Key)",
                    }
                ),
                401,
            )

        # Verify empresa exists
        empresa = get_empresa_by_id(api_key)
        if not empresa:
            return jsonify({"success": False, "error": "Invalid API key"}), 401

        # Verify suscripcionActiva is True
        if not empresa.get("suscripcionActiva", False):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Active subscription required to use the API",
                    }
                ),
                403,
            )

        # Pass empresa_id to the route function
        return f(empresa_id=api_key, empresa=empresa, *args, **kwargs)

    return decorated_function


@app.route("/api/vacantes", methods=["GET"])
@require_api_key
def api_get_vacantes(empresa_id, empresa):
    """
    GET /api/vacantes
    Retrieves all vacantes for the authenticated empresa.
    """
    try:
        # Get all vacantes for this empresa
        vacantes = get_vacantes_by_empresa_id(empresa_id)

        # Convert vacantes to JSON-serializable format
        vacantes_list = []
        for vacante in vacantes:
            vacante_dict = {
                "id": vacante.get("id"),
                "titulo": vacante.get("titulo"),
                "descripcion": vacante.get("descripcion"),
                "requisitos": vacante.get("requisitos"),
                "modalidad": vacante.get("modalidad"),
                "tipoContrato": vacante.get("tipoContrato"),
                "duracion": vacante.get("duracion"),
                "horario": vacante.get("horario"),
                "sueldo": vacante.get("sueldo"),
                "educacion": vacante.get("educación"),
                "experienciaRequerida": vacante.get("experienciaRequerida"),
                "habilidadesDuras": vacante.get("habilidadesDuras", []),
                "idiomas": vacante.get("idiomas", []),
                "nombreEmpresa": vacante.get("nombreEmpresa"),
                "activa": vacante.get("activa", True),
            }
            vacantes_list.append(vacante_dict)

        return (
            jsonify(
                {
                    "success": True,
                    "count": len(vacantes_list),
                    "vacantes": vacantes_list,
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"Internal server error: {str(e)}"}),
            500,
        )


@app.route("/api/vacante", methods=["POST"])
@require_api_key
def api_create_vacante(empresa_id, empresa):
    """
    POST /api/vacante
    Creates a new vacante for the authenticated empresa.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        # Validate required field: titulo
        if not data.get("titulo"):
            return (
                jsonify({"success": False, "error": "Field 'titulo' is required"}),
                400,
            )

        # Prepare vacante data
        vacante_data = {
            "titulo": data.get("titulo", ""),
            "descripcion": data.get("descripcion", ""),
            "requisitos": data.get("requisitos", ""),
            "modalidad": data.get("modalidad", ""),
            "tipoContrato": data.get("tipoContrato", ""),
            "duracion": data.get("duracion", ""),
            "horario": data.get("horario", ""),
            "sueldo": data.get("sueldo"),
            "educacion": data.get("educacion", ""),
            "experienciaRequerida": data.get("experienciaRequerida", ""),
            "habilidadesDuras": data.get("habilidadesDuras", []),
            "idiomas": data.get("idiomas", []),
            "nombreEmpresa": empresa.get("nombre", ""),
            "activa": data.get("activa", True),
        }

        # Create the vacante
        vacante_id = create_vacante(empresa_id, vacante_data)

        if vacante_id:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Vacante created successfully",
                        "vacante_id": vacante_id,
                    }
                ),
                201,
            )
        else:
            return jsonify({"success": False, "error": "Failed to create vacante"}), 500

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"Internal server error: {str(e)}"}),
            500,
        )


@app.route("/api/vacante/<vacante_id>", methods=["PUT"])
@require_api_key
def api_update_vacante(empresa_id, empresa, vacante_id):
    """
    PUT /api/vacante/{id}
    Updates an existing vacante by ID.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        # Verify the vacante belongs to the empresa
        if not verify_vacante_belongs_to_empresa(vacante_id, empresa_id):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Vacante not found or does not belong to your empresa",
                    }
                ),
                404,
            )

        # Prepare update data (only include provided fields)
        vacante_data = {}

        allowed_fields = [
            "titulo",
            "descripcion",
            "requisitos",
            "modalidad",
            "tipoContrato",
            "duracion",
            "horario",
            "sueldo",
            "educacion",
            "experienciaRequerida",
            "habilidadesDuras",
            "idiomas",
            "nombreEmpresa",
            "activa",
        ]

        for field in allowed_fields:
            if field in data:
                vacante_data[field] = data[field]

        if not vacante_data:
            return (
                jsonify(
                    {"success": False, "error": "No valid fields provided for update"}
                ),
                400,
            )

        # Update the vacante
        if update_vacante(vacante_id, vacante_data):
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Vacante updated successfully",
                        "vacante_id": vacante_id,
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to update vacante"}), 500

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"Internal server error: {str(e)}"}),
            500,
        )


@app.route("/api/vacante/<vacante_id>", methods=["DELETE"])
@require_api_key
def api_delete_vacante(empresa_id, empresa, vacante_id):
    """
    DELETE /api/vacante/{id}
    Deletes a vacante by ID.
    """
    try:
        # Verify the vacante belongs to the empresa
        if not verify_vacante_belongs_to_empresa(vacante_id, empresa_id):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Vacante not found or does not belong to your empresa",
                    }
                ),
                404,
            )

        # Delete the vacante
        if delete_vacante(vacante_id):
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Vacante deleted successfully",
                        "vacante_id": vacante_id,
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to delete vacante"}), 500

    except Exception as e:
        return (
            jsonify({"success": False, "error": f"Internal server error: {str(e)}"}),
            500,
        )


if __name__ == "__main__":
    app.run(debug=True)
