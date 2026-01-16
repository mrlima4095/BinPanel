from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# Models para autenticação
class LoginRequest(BaseModel):
    dominio: str
    username: str
    senha: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    usuario_id: int
    empresa_id: Optional[int] = None
    hierarquia: int
    username: str

# Models para usuários
class UsuarioCreate(BaseModel):
    username: str
    email: EmailStr
    senha: str
    hierarquia: int = 7
    cargo_personalizado: Optional[str] = None
    permissoes: Optional[List[str]] = []

class UsuarioUpdate(BaseModel):
    email: Optional[EmailStr] = None
    hierarquia: Optional[int] = None
    cargo_personalizado: Optional[str] = None
    permissoes: Optional[List[str]] = None
    ativo: Optional[bool] = None

class UsuarioResponse(BaseModel):
    id: int
    username: str
    email: str
    hierarquia: int
    cargo_personalizado: Optional[str]
    empresa_id: Optional[int]
    ativo: bool
    criado_em: datetime

# Models para empresas
class EmpresaCreate(BaseModel):
    nome: str
    dominio: str
    config: Optional[Dict[str, Any]] = {}

class EmpresaResponse(BaseModel):
    id: int
    nome: str
    dominio: str
    ativo: bool
    config: Dict[str, Any]
    criado_em: datetime

# Models para emails
class EmailSend(BaseModel):
    destinatario: EmailStr
    assunto: str
    corpo: str

class EmailResponse(BaseModel):
    id: int
    remetente: str
    destinatario: str
    assunto: str
    corpo: str
    lida: bool
    criado_em: datetime

# Models para hierarquias
class HierarquiaCreate(BaseModel):
    nome: str
    nivel: int
    permissoes: List[str] = []

class HierarquiaResponse(BaseModel):
    id: int
    nome: str
    nivel: int
    permissoes: List[str]
    empresa_id: int