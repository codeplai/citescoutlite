import bcrypt
from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import Optional, Dict

class Autenticacion:
    def __init__(self, secret_key: str = "agroscout-secret-key-change-in-production"):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.token_expiration_hours = 24

    def hash_password(self, password: str) -> str:
        """Hashea una contraseña con bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verificar_password(self, password: str, hashed: str) -> bool:
        """Verifica si una contraseña coincide con su hash bcrypt."""
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

    def generar_token(self, user_id: int, email: str, org_id: Optional[int] = None) -> str:
        """Genera un JWT con expiración."""
        expires_at = datetime.utcnow() + timedelta(hours=self.token_expiration_hours)
        payload = {
            "user_id": user_id,
            "email": email,
            "org_id": org_id,
            "exp": expires_at
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verificar_token(self, token: str) -> Optional[Dict]:
        """Verifica un JWT y retorna el payload."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    def extraer_bearer_token(self, authorization: Optional[str]) -> Optional[str]:
        """Extrae el token del header 'Authorization: Bearer <token>'."""
        if not authorization:
            return None
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1]
