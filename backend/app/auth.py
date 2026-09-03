"""
Autenticação e controle de acesso hierárquico.

Hierarquia (decisão do time):
  DIRETOR       -> vê e administra tudo. Único que pode criar/gerenciar
                    coordenadores e outros diretores.
  COORDENADOR   -> vê seus próprios projetos + os de todos os analistas
                    sob ele (manager_id aponta pro coordenador). Só pode
                    criar/gerenciar analistas da própria equipe.
  ANALISTA      -> vê e mexe só nos próprios projetos. Não gerencia ninguém.

Modelo fechado, sem auto-cadastro. O primeiro usuário (sempre DIRETOR) é
criado via bootstrap (uma vez só, protegido por secret de ambiente).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.db import User, get_db

SECRET_KEY = os.environ.get("TACELERAR_JWT_SECRET")
if not SECRET_KEY:
    # Só cai aqui em dev local. Em qualquer ambiente compartilhado, definir
    # TACELERAR_JWT_SECRET é obrigatório (ver .env.example) — sem isso, tokens
    # emitidos antes de um restart do processo deixam de ser verificáveis
    # (e um secret previsível permite forjar token de diretor).
    SECRET_KEY = "dev-insecure-secret-troque-em-producao"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12h

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_MAX_PASSWORD_BYTES = 72  # limite físico do bcrypt


class Role(str, Enum):
    DIRETOR = "diretor"
    COORDENADOR = "coordenador"
    ANALISTA = "analista"


ROLES = {r.value for r in Role}


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.checkpw(truncated, hashed.encode("utf-8"))


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user.id, "email": user.email, "role": user.role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, email: str, name: str, password: str,
                 role: str, manager_id: str | None = None) -> User:
    user = User(
        id=str(uuid.uuid4()), email=email, name=name,
        password_hash=hash_password(password), role=role, manager_id=manager_id,
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


def get_current_diretor(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.DIRETOR:
        raise HTTPException(403, "Requer perfil de diretor.")
    return user


def get_current_coordenador_ou_acima(user: User = Depends(get_current_user)) -> User:
    if user.role not in (Role.DIRETOR, Role.COORDENADOR):
        raise HTTPException(403, "Requer perfil de coordenador ou diretor.")
    return user


# ---------- Visibilidade hierárquica ----------

def visible_owner_ids(db: Session, user: User) -> set[str] | None:
    """IDs de usuário cujos projetos este usuário pode ver/acessar.

    Retorna None para 'sem restrição' (diretor vê tudo — mais barato do
    que materializar todos os ids). Coordenador vê a própria conta + a
    equipe direta (analistas com manager_id == user.id). Analista só vê
    a própria conta.
    """
    if user.role == Role.DIRETOR:
        return None
    if user.role == Role.COORDENADOR:
        team = db.query(User.id).filter(User.manager_id == user.id).all()
        return {user.id, *(row[0] for row in team)}
    return {user.id}


def can_see_owner(db: Session, user: User, owner_id: str | None) -> bool:
    ids = visible_owner_ids(db, user)
    return ids is None or owner_id in ids
