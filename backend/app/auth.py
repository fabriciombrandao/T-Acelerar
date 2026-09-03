"""
Autenticação — necessária a partir do momento em que a aplicação roda em VPS
compartilhado por vários consultores (decisão registrada em conversa com o
time: >5 consultores, projetos de cliente simultâneos, dado sensível).

Modelo: time fechado, sem auto-cadastro. O primeiro admin é criado via
bootstrap (uma vez só, protegido por secret de ambiente); depois disso,
admin cria os demais usuários. JWT com expiração curta (12h por padrão).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.db import User, get_db

SECRET_KEY = os.environ.get("WINTHOR_JWT_SECRET")
if not SECRET_KEY:
    # Só cai aqui em dev local. Em qualquer ambiente compartilhado, definir
    # WINTHOR_JWT_SECRET é obrigatório (ver .env.example) — sem isso, tokens
    # emitidos antes de um restart do processo deixam de ser verificáveis
    # (e um secret previsível permite forjar token de admin).
    SECRET_KEY = "dev-insecure-secret-troque-em-producao"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12h

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# bcrypt tem limite de 72 bytes por senha — truncamos deliberadamente em vez
# de deixar a lib estourar exceção (passlib fazia isso automaticamente;
# usamos bcrypt direto por incompatibilidade do passlib com bcrypt>=4.0).
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(truncated, hashed.encode("utf-8"))


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user.id, "email": user.email, "is_admin": user.is_admin, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, email: str, name: str, password: str, is_admin: bool = False) -> User:
    user = User(
        id=str(uuid.uuid4()), email=email, name=name,
        password_hash=hash_password(password), is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        401, "Credenciais inválidas ou expiradas.", headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Requer permissão de administrador.")
    return user
