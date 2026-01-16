from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import database
from models import *
from auth import *
import email_server
import json
from typing import List
import threading

app = FastAPI(title="BinPanel API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar banco de dados
database.init_database()

# Iniciar servidor de email em thread separada
email_thread = threading.Thread(target=email_server.start_email_server, daemon=True)
email_thread.start()

# Rotas de autenticação
@app.post("/api/auth/login", response_model=Token)
async def login(login_data: LoginRequest):
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar empresa pelo domínio
        cursor.execute("SELECT id FROM empresas WHERE dominio = ?", (login_data.dominio,))
        empresa = cursor.fetchone()
        empresa_id = empresa["id"] if empresa else None
        
        # Buscar usuário
        if empresa_id:
            cursor.execute(
                "SELECT id, senha_hash, hierarquia, username FROM usuarios WHERE username = ? AND empresa_id = ?",
                (login_data.username, empresa_id)
            )
        else:
            # Admin master (sem empresa)
            cursor.execute(
                "SELECT id, senha_hash, hierarquia, username FROM usuarios WHERE username = ? AND empresa_id IS NULL",
                (login_data.username,)
            )
        
        usuario = cursor.fetchone()
        
        if not usuario or not verify_password(login_data.senha, usuario["senha_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas"
            )
        
        # Criar tokens
        token_data = {
            "sub": usuario["id"],
            "username": usuario["username"],
            "empresa_id": empresa_id,
            "hierarquia": usuario["hierarquia"]
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Salvar refresh token
        cursor.execute('''
            INSERT INTO tokens (usuario_id, token, refresh_token, expira_em)
            VALUES (?, ?, ?, datetime('now', '+7 days'))
        ''', (usuario["id"], access_token, refresh_token))
        conn.commit()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM tokens WHERE refresh_token = ? AND expira_em > datetime('now')",
                (refresh_token,)
            )
            token_record = cursor.fetchone()
            
            if not token_record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token inválido ou expirado"
                )
            
            # Buscar usuário
            cursor.execute(
                "SELECT id, username, empresa_id, hierarquia FROM usuarios WHERE id = ?",
                (payload["sub"],)
            )
            usuario = cursor.fetchone()
            
            if not usuario:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuário não encontrado"
                )
            
            # Criar novos tokens
            token_data = {
                "sub": usuario["id"],
                "username": usuario["username"],
                "empresa_id": usuario["empresa_id"],
                "hierarquia": usuario["hierarquia"]
            }
            
            new_access_token = create_access_token(token_data)
            new_refresh_token = create_refresh_token(token_data)
            
            # Atualizar tokens
            cursor.execute('''
                UPDATE tokens 
                SET token = ?, refresh_token = ?, expira_em = datetime('now', '+7 days')
                WHERE id = ?
            ''', (new_access_token, new_refresh_token, token_record["id"]))
            conn.commit()
            
            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer"
            }
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

# Rotas de usuários
@app.get("/api/usuarios", response_model=List[UsuarioResponse])
async def listar_usuarios(
    current_user: TokenData = Depends(get_current_user),
    empresa_id: Optional[int] = None
):
    check_permission(current_user, 2)  # Apenas admin da empresa ou superior
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        if current_user.hierarquia == 1:  # Admin total
            if empresa_id:
                cursor.execute(
                    "SELECT * FROM usuarios WHERE empresa_id = ? ORDER BY hierarquia",
                    (empresa_id,)
                )
            else:
                cursor.execute("SELECT * FROM usuarios ORDER BY hierarquia")
        else:  # Admin da empresa
            cursor.execute(
                "SELECT * FROM usuarios WHERE empresa_id = ? ORDER BY hierarquia",
                (current_user.empresa_id,)
            )
        
        usuarios = cursor.fetchall()
        return [dict(u) for u in usuarios]

@app.post("/api/usuarios", response_model=UsuarioResponse)
async def criar_usuario(
    usuario: UsuarioCreate,
    current_user: TokenData = Depends(get_current_user)
):
    check_permission(current_user, 2)
    
    # Verificar se email já existe
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (usuario.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado"
            )
        
        # Determinar empresa_id
        empresa_id = current_user.empresa_id if current_user.hierarquia > 1 else None
        
        # Hash da senha
        senha_hash = get_password_hash(usuario.senha)
        
        # Inserir usuário
        cursor.execute('''
            INSERT INTO usuarios (empresa_id, username, email, senha_hash, hierarquia, 
                                cargo_personalizado, permissoes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            empresa_id,
            usuario.username,
            usuario.email,
            senha_hash,
            usuario.hierarquia,
            usuario.cargo_personalizado,
            json.dumps(usuario.permissoes)
        ))
        
        usuario_id = cursor.lastrowid
        
        # Buscar usuário criado
        cursor.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        novo_usuario = cursor.fetchone()
        
        conn.commit()
        
        return dict(novo_usuario)

# Rotas de empresas
@app.get("/api/empresas", response_model=List[EmpresaResponse])
async def listar_empresas(current_user: TokenData = Depends(get_current_user)):
    check_permission(current_user, 1)  # Apenas admin total
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM empresas ORDER BY nome")
        empresas = cursor.fetchall()
        return [dict(e) for e in empresas]

@app.post("/api/empresas", response_model=EmpresaResponse)
async def criar_empresa(
    empresa: EmpresaCreate,
    current_user: TokenData = Depends(get_current_user)
):
    check_permission(current_user, 1)
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se domínio já existe
        cursor.execute("SELECT id FROM empresas WHERE dominio = ?", (empresa.dominio,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domínio já cadastrado"
            )
        
        # Inserir empresa
        cursor.execute('''
            INSERT INTO empresas (nome, dominio, config)
            VALUES (?, ?, ?)
        ''', (empresa.nome, empresa.dominio, json.dumps(empresa.config)))
        
        empresa_id = cursor.lastrowid
        
        # Buscar empresa criada
        cursor.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,))
        nova_empresa = cursor.fetchone()
        
        conn.commit()
        
        return dict(nova_empresa)

# Rotas de emails
@app.get("/api/emails", response_model=List[EmailResponse])
async def listar_emails(
    current_user: TokenData = Depends(get_current_user),
    lida: Optional[bool] = None
):
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar email do usuário
        cursor.execute("SELECT email FROM usuarios WHERE id = ?", (current_user.usuario_id,))
        usuario_email = cursor.fetchone()["email"]
        
        query = "SELECT * FROM emails WHERE destinatario = ?"
        params = [usuario_email]
        
        if lida is not None:
            query += " AND lida = ?"
            params.append(lida)
        
        query += " ORDER BY criado_em DESC"
        cursor.execute(query, tuple(params))
        emails = cursor.fetchall()
        
        return [dict(e) for e in emails]

@app.post("/api/emails/send")
async def enviar_email(
    email: EmailSend,
    current_user: TokenData = Depends(get_current_user)
):
    # Buscar email do remetente
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM usuarios WHERE id = ?", (current_user.usuario_id,))
        remetente_email = cursor.fetchone()["email"]
    
    # Enviar email
    success = email_server.send_email(
        to_email=email.destinatario,
        subject=email.assunto,
        body=email.corpo,
        from_email=remetente_email
    )
    
    if success:
        return {"message": "Email enviado com sucesso"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao enviar email"
        )

# Rotas de hierarquias
@app.get("/api/hierarquias/{empresa_id}", response_model=List[HierarquiaResponse])
async def listar_hierarquias(
    empresa_id: int,
    current_user: TokenData = Depends(get_current_user)
):
    check_permission(current_user, 2)
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM hierarquias_empresa WHERE empresa_id = ? ORDER BY nivel",
            (empresa_id,)
        )
        hierarquias = cursor.fetchall()
        return [dict(h) for h in hierarquias]

@app.post("/api/hierarquias/{empresa_id}", response_model=HierarquiaResponse)
async def criar_hierarquia(
    empresa_id: int,
    hierarquia: HierarquiaCreate,
    current_user: TokenData = Depends(get_current_user)
):
    check_permission(current_user, 2)
    
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se nível já existe
        cursor.execute(
            "SELECT id FROM hierarquias_empresa WHERE empresa_id = ? AND nivel = ?",
            (empresa_id, hierarquia.nivel)
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nível já existe"
            )
        
        # Inserir hierarquia
        cursor.execute('''
            INSERT INTO hierarquias_empresa (empresa_id, nome, nivel, permissoes)
            VALUES (?, ?, ?, ?)
        ''', (
            empresa_id,
            hierarquia.nome,
            hierarquia.nivel,
            json.dumps(hierarquia.permissoes)
        ))
        
        hierarquia_id = cursor.lastrowid
        
        # Buscar hierarquia criada
        cursor.execute("SELECT * FROM hierarquias_empresa WHERE id = ?", (hierarquia_id,))
        nova_hierarquia = cursor.fetchone()
        
        conn.commit()
        
        return dict(nova_hierarquia)

# Rota para servir frontend
@app.get("/{path:path}")
async def serve_frontend(path: str):
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)