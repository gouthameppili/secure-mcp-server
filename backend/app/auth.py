import os
import datetime
from datetime import timezone, timedelta
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load environment variables
load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

# Reusable security dependency provider
security = HTTPBearer()

def create_access_token(user_id: str, expires_delta: timedelta = None) -> str:
    """
    Generates a JWT access token with a specified userId payload.
    """
    if expires_delta:
        expire = datetime.datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(timezone.utc) + timedelta(minutes=60)
        
    payload = {
        "userId": user_id,
        "exp": expire,
        "iat": datetime.datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def verify_access_token(token: str) -> str:
    """
    Decodes the token, handles expired or invalid signatures,
    and extracts and returns the 'userId'.
    Raises HTTPException with a 401 status on verification failure.
    """
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured on the server."
        )
        
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("userId")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: userId claim is missing.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI dependency provider that extracts the Bearer token from the incoming
    HTTP request header, verifies it, and returns the verified string 'userId'.
    """
    token = credentials.credentials
    return verify_access_token(token)
