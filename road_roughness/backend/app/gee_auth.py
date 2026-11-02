"""Google Earth Engine authentication helper for cloud deployments."""
import os
import json
import ee
from pathlib import Path


def initialize_earth_engine(project_id: str):
    """Initialize Earth Engine with appropriate authentication method.
    
    Args:
        project_id: Google Earth Engine project ID
        
    Tries multiple authentication methods:
    1. Service account JSON from environment variable
    2. Service account JSON from file path
    3. Default credentials (for local development)
    """
    
    # Method 1: Service account JSON in environment variable
    service_account_json = os.getenv("GEE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            credentials_dict = json.loads(service_account_json)
            service_account = credentials_dict.get("client_email")
            credentials = ee.ServiceAccountCredentials(service_account, key_data=service_account_json)
            ee.Initialize(credentials, project=project_id)
            print(f"✓ Earth Engine initialized with service account from env var")
            return
        except Exception as e:
            print(f"⚠ Failed to initialize EE with service account JSON from env: {e}")
    
    # Method 2: Service account JSON file
    service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if service_account_file and Path(service_account_file).exists():
        try:
            with open(service_account_file) as f:
                credentials_dict = json.load(f)
            service_account = credentials_dict.get("client_email")
            credentials = ee.ServiceAccountCredentials(service_account, service_account_file)
            ee.Initialize(credentials, project=project_id)
            print(f"✓ Earth Engine initialized with service account from file")
            return
        except Exception as e:
            print(f"⚠ Failed to initialize EE with service account file: {e}")
    
    # Method 3: Default authentication (local development)
    try:
        ee.Initialize(project=project_id)
        print(f"✓ Earth Engine initialized with default credentials")
        return
    except Exception as e:
        print(f"⚠ Failed to initialize EE with default credentials: {e}")
    
    # If all methods fail, raise an error
    raise RuntimeError(
        "Failed to initialize Google Earth Engine. Please set one of:\n"
        "  - GEE_SERVICE_ACCOUNT_JSON environment variable with service account JSON\n"
        "  - GOOGLE_APPLICATION_CREDENTIALS environment variable pointing to service account file\n"
        "  - Run 'earthengine authenticate' for local development"
    )
