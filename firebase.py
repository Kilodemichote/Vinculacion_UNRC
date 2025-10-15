import firebase_admin
from firebase_admin import credentials, auth, firestore
import os

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using a service account.
    """
    try:
        # Get the path to the service account key from environment variables
        service_account_key_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not service_account_key_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
            
        # Ensure the path is absolute or relative to the project root
        if not os.path.isabs(service_account_key_path):
            service_account_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), service_account_key_path)
            
        cred = credentials.Certificate(service_account_key_path)
        firebase_admin.initialize_app(cred) 
        print("Firebase Admin SDK initialized successfully.") 
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")

def upsert_empresa_email(email):
    """
    Upsert empresa email to Firestore empresas collection
    """
    try:
        db = firestore.client()
        empresas_ref = db.collection('empresas')
        
        # Use email as document ID (sanitized)
        doc_id = email.replace('.', '_').replace('@', '_at_')
        
        empresas_ref.document(doc_id).set({
            'email': email,
            'updated_at': firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        print(f"Empresa email upserted: {email}")
    except Exception as e:
        print(f"Error upserting empresa email: {e}")

def verify_google_id_token(id_token):
    """
    Verifies the Google ID token sent from the client.
    Returns the decoded token (user info) if valid, otherwise None.
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"Error verifying ID token: {e}")
        return None