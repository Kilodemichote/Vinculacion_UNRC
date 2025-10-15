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

def get_empresa_by_correo(correo):
    """
    Retrieves empresa document by correo (email).
    Returns the document data if found, otherwise None.
    """
    try:
        db = firestore.client()
        empresas_ref = db.collection('empresas')

        # Query by correo field
        query = empresas_ref.where('correo', '==', correo).limit(1)
        docs = query.stream()

        for doc in docs:
            data = doc.to_dict()
            data['doc_id'] = doc.id  # Include document ID for updates
            return data

        return None
    except Exception as e:
        print(f"Error retrieving empresa by correo: {e}")
        return None

def create_empresa(correo):
    """
    Creates a new empresa document with just the correo field.
    Uses automatic document ID assignment.
    Returns the document ID if successful, otherwise None.
    """
    try:
        db = firestore.client()
        empresas_ref = db.collection('empresas')

        # Create new document with auto-generated ID
        doc_ref = empresas_ref.document()
        doc_ref.set({
            'correo': correo,
            'contactoPrincipal': None,
            'estado': None,
            'giro': None,
            'mun_alcaldia': None,
            'nombre': None,
            'suscripcionActiva': False,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        })

        print(f"New empresa created with correo: {correo}, doc_id: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        print(f"Error creating empresa: {e}")
        return None

def update_empresa(doc_id, data):
    """
    Updates an existing empresa document.
    data should be a dict with the fields to update.
    Returns True if successful, False otherwise.
    """
    try:
        db = firestore.client()
        empresas_ref = db.collection('empresas')

        # Add timestamp to the update
        data['updated_at'] = firestore.SERVER_TIMESTAMP

        # Update the document
        empresas_ref.document(doc_id).update(data)

        print(f"Empresa document {doc_id} updated successfully")
        return True
    except Exception as e:
        print(f"Error updating empresa: {e}")
        return False

def get_vacantes_by_empresa_id(empresa_doc_id):
    """
    Retrieves all vacantes (job opportunities) for a specific empresa.
    Returns a list of vacante documents.
    """
    try:
        db = firestore.client()
        vacantes_ref = db.collection('vacantes')
        empresas_ref = db.collection('empresas')

        # Create a reference to the empresa document
        empresa_ref = empresas_ref.document(empresa_doc_id)

        # Query vacantes where empresaId equals the empresa reference
        query = vacantes_ref.where('empresaId', '==', empresa_ref)
        docs = query.stream()

        vacantes = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id  # Include document ID
            vacantes.append(data)

        return vacantes
    except Exception as e:
        print(f"Error retrieving vacantes by empresa ID: {e}")
        return []

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