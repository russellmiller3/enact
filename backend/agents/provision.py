"""
Provisioning Agent: JWT token generation (mock IAM)
Only runs if decision == APPROVE
"""
import time
import secrets
from datetime import datetime, timedelta
from jose import jwt
from models import ProvisionResult

# Mock JWT secret (in production, use env var)
SECRET_KEY = "demo-secret-key-do-not-use-in-prod"
ALGORITHM = "HS256"

def run_provision(requester_email: str, dataset_name: str, access_level: str) -> ProvisionResult:
    """
    Generate JWT access token with 90-day expiry
    Mock IAM integration
    """
    print("\n" + "="*60)
    print("🔑 PROVISIONING AGENT - Generating access token")
    print("="*60)
    print(f"👤 User: {requester_email}")
    print(f"📊 Dataset: {dataset_name}")
    print(f"🔐 Access Level: {access_level.upper()}")
    
    start_time = time.time()
    
    # Calculate expiry (90 days from now)
    expiry_date = datetime.utcnow() + timedelta(days=90)
    expiry_str = expiry_date.strftime("%Y-%m-%d")
    print(f"⏰ Expiry: {expiry_str} (90 days)")
    
    # Generate JWT payload
    payload = {
        "sub": requester_email,
        "dataset": dataset_name,
        "access_level": access_level,
        "exp": expiry_date.timestamp(),
        "iat": datetime.utcnow().timestamp(),
        "jti": f"visa-token-{secrets.randbelow(100000):05d}"
    }
    
    # Encode token
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    # Mock: Log would-be IAM API call
    print(f"🔌 [MOCK IAM API] POST /api/v1/access-grants")
    print(f"   Payload: sub={requester_email}, dataset={dataset_name}, jti={payload['jti']}")
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    print(f"✓ JWT token generated ({len(token)} chars)")
    print(f"⏱️  Provisioning completed in {duration_ms}ms")
    print("="*60 + "\n")
    
    return ProvisionResult(
        duration_ms=duration_ms,
        token=token,
        expires_at=expiry_str
    )
