import re
import hashlib
import secrets
from functools import wraps
from flask import session, request, jsonify, flash, redirect, url_for
from datetime import datetime, timedelta

class AuthManager:
    def __init__(self):
        self.failed_attempts = {}  # Store failed login attempts
        self.reset_tokens = {}     # Store password reset tokens
        
    def validate_email(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_password(self, password):
        """Validate password strength"""
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"
        
        if not re.search(r'[A-Z]', password):
            return False, "La contraseña debe contener al menos una mayúscula"
        
        if not re.search(r'[a-z]', password):
            return False, "La contraseña debe contener al menos una minúscula"
        
        if not re.search(r'\d', password):
            return False, "La contraseña debe contener al menos un número"
        
        return True, "Contraseña válida"
    
    def hash_password(self, password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return salt + password_hash.hex()
    
    def verify_password(self, stored_password, provided_password):
        """Verify password against stored hash"""
        salt = stored_password[:32]
        stored_hash = stored_password[32:]
        password_hash = hashlib.pbkdf2_hmac('sha256',
                                          provided_password.encode('utf-8'),
                                          salt.encode('utf-8'),
                                          100000)
        return stored_hash == password_hash.hex()
    
    def is_account_locked(self, email):
        """Check if account is temporarily locked due to failed attempts"""
        if email in self.failed_attempts:
            attempts, last_attempt = self.failed_attempts[email]
            if attempts >= 5:
                # Lock for 30 minutes after 5 failed attempts
                if datetime.now() - last_attempt < timedelta(minutes=30):
                    return True
                else:
                    # Reset failed attempts after lock period
                    del self.failed_attempts[email]
        return False
    
    def record_failed_attempt(self, email):
        """Record a failed login attempt"""
        if email in self.failed_attempts:
            attempts, _ = self.failed_attempts[email]
            self.failed_attempts[email] = (attempts + 1, datetime.now())
        else:
            self.failed_attempts[email] = (1, datetime.now())
    
    def clear_failed_attempts(self, email):
        """Clear failed attempts on successful login"""
        if email in self.failed_attempts:
            del self.failed_attempts[email]
    
    def generate_reset_token(self, email):
        """Generate password reset token"""
        token = secrets.token_urlsafe(32)
        self.reset_tokens[token] = {
            'email': email,
            'expires': datetime.now() + timedelta(hours=1)
        }
        return token
    
    def validate_reset_token(self, token):
        """Validate password reset token"""
        if token in self.reset_tokens:
            token_data = self.reset_tokens[token]
            if datetime.now() < token_data['expires']:
                return token_data['email']
            else:
                del self.reset_tokens[token]
        return None
    
    def sanitize_input(self, input_string):
        """Basic input sanitization"""
        if not input_string:
            return ""
        return input_string.strip()

# Global auth manager instance
auth_manager = AuthManager()

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('alumnos_login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_login_form(email, password):
    """Validate login form data"""
    errors = []
    
    # Sanitize inputs
    email = auth_manager.sanitize_input(email)
    password = auth_manager.sanitize_input(password)
    
    # Check if fields are empty
    if not email:
        errors.append("El campo de usuario (email) es obligatorio")
    
    if not password:
        errors.append("El campo de contraseña es obligatorio")
    
    # Validate email format
    if email and not auth_manager.validate_email(email):
        errors.append("Por favor, ingresa un email válido")
    
    # Check if account is locked
    if email and auth_manager.is_account_locked(email):
        errors.append("Cuenta temporalmente bloqueada debido a múltiples intentos fallidos. Inténtalo en 30 minutos.")
    
    return errors, email, password

def validate_register_form(email, password, confirm_password):
    """Validate registration form data"""
    errors = []
    
    # Sanitize inputs
    email = auth_manager.sanitize_input(email)
    password = auth_manager.sanitize_input(password)
    confirm_password = auth_manager.sanitize_input(confirm_password)
    
    # Check if fields are empty
    if not email:
        errors.append("El campo de email es obligatorio")
    
    if not password:
        errors.append("El campo de contraseña es obligatorio")
    
    if not confirm_password:
        errors.append("Debes confirmar tu contraseña")
    
    # Validate email format
    if email and not auth_manager.validate_email(email):
        errors.append("Por favor, ingresa un email válido")
    
    # Validate password strength
    if password:
        is_valid, message = auth_manager.validate_password(password)
        if not is_valid:
            errors.append(message)
    
    # Check password confirmation
    if password and confirm_password and password != confirm_password:
        errors.append("Las contraseñas no coinciden")
    
    return errors, email, password

# Firebase integration functions (to be implemented)
def authenticate_user_firebase(email, password):
    """
    Authenticate user with Firebase
    This is a placeholder - implement with actual Firebase Auth
    """
    # TODO: Implement Firebase authentication
    # For now, return mock data for testing
    
    # Mock user for testing
    if email == "test@ejemplo.com" and password == "Test123456":
        return {
            'user_id': 'mock_user_123',
            'email': email,
            'name': 'Usuario de Prueba',
            'role': 'alumno'
        }
    return None

def create_user_firebase(email, password):
    """
    Create new user in Firebase
    This is a placeholder - implement with actual Firebase Auth
    """
    # TODO: Implement Firebase user creation
    # For now, return mock success for testing
    
    # Hash password for storage
    hashed_password = auth_manager.hash_password(password)
    
    # Mock user creation
    return {
        'user_id': f'user_{secrets.token_hex(8)}',
        'email': email,
        'name': email.split('@')[0],
        'role': 'alumno',
        'created_at': datetime.now().isoformat()
    }

def send_password_reset_email(email, reset_token):
    """
    Send password reset email
    This is a placeholder - implement with actual email service
    """
    # TODO: Implement email sending functionality
    print(f"Password reset email sent to {email} with token: {reset_token}")
    return True