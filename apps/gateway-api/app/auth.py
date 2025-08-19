from jose import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
import structlog

from app.config import settings
from app.database import get_db
from app.models import User

logger = structlog.get_logger()

security = HTTPBearer()

class AuthService:
    """Authentication service using Google OAuth and JWT"""
    
    def __init__(self):
        self.google_client_id = settings.google_client_id
        self.jwt_secret = settings.jwt_secret
        self.jwt_algorithm = settings.jwt_algorithm
        self.jwt_expiration_hours = settings.jwt_expiration_hours
    
    async def verify_google_token(self, token: str) -> Dict[str, Any]:
        """Verify Google ID token and return user info"""
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), self.google_client_id
            )
            
            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            
            return {
                'id': idinfo['sub'],
                'email': idinfo['email'],
                'name': idinfo['name'],
                'picture': idinfo.get('picture'),
                'verified_email': idinfo.get('email_verified', False)
            }
            
        except ValueError as e:
            logger.error("Google token verification failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )
    
    async def get_or_create_user(self, google_user_info: Dict[str, Any], db: AsyncSession) -> User:
        """Get existing user or create new one from Google user info"""
        
        # Check if user exists
        query = select(User).where(User.email == google_user_info['email'])
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            # Update user info if needed
            updated = False
            if user.name != google_user_info['name']:
                user.name = google_user_info['name']
                updated = True
            if user.picture != google_user_info.get('picture'):
                user.picture = google_user_info.get('picture')
                updated = True
            if user.verified_email != google_user_info.get('verified_email', False):
                user.verified_email = google_user_info.get('verified_email', False)
                updated = True
            
            if updated:
                user.updated_at = datetime.now(timezone.utc)
                await db.commit()
                
            return user
        
        # Create new user
        user_data = {
            'email': google_user_info['email'],
            'name': google_user_info['name'],
            'picture': google_user_info.get('picture'),
            'verified_email': google_user_info.get('verified_email', False),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        result = await db.execute(insert(User).values(**user_data).returning(User))
        user = result.scalar_one()
        await db.commit()
        
        logger.info("Created new user", email=user.email, user_id=str(user.id))
        return user
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token for user"""
        payload = {
            'sub': str(user.id),
            'email': user.email,
            'name': user.name,
            'exp': datetime.now(timezone.utc) + timedelta(hours=self.jwt_expiration_hours),
            'iat': datetime.now(timezone.utc)
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT access token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def get_current_user(self, token_payload: Dict[str, Any], db: AsyncSession) -> User:
        """Get current user from token payload"""
        user_id = token_payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user

# Global auth service instance
auth_service = AuthService()

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> User:
    """Dependency to get current authenticated user"""
    token = None

    # Try to get token from httpOnly cookie first
    if "access_token" in request.cookies:
        token = request.cookies["access_token"]
    # Fallback to Authorization header for backward compatibility
    elif credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided"
        )

    payload = auth_service.verify_access_token(token)
    return await auth_service.get_current_user(payload, db)

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """Dependency to get current user if authenticated, None otherwise"""
    token = None

    # Try to get token from httpOnly cookie first
    if "access_token" in request.cookies:
        token = request.cookies["access_token"]
    # Fallback to Authorization header for backward compatibility
    elif credentials:
        token = credentials.credentials

    if not token:
        return None

    try:
        payload = auth_service.verify_access_token(token)
        return await auth_service.get_current_user(payload, db)
    except HTTPException:
        return None
