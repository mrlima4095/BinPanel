#!/usr/bin/env python3
import sqlite3
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import threading
import socketserver
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Configurações
DATABASE = "binpanel.db"
SECRET_KEY = "binpanel_secret_key_change_in_production"
PORT = 8000

# Inicializar banco de dados
def init_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            dominio TEXT UNIQUE NOT NULL,
            ativo INTEGER DEFAULT 1,
            config TEXT DEFAULT '{}',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            hierarquia INTEGER DEFAULT 7,
            cargo_personalizado TEXT,
            permissoes TEXT DEFAULT '[]',
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id),
            UNIQUE(empresa_id, username),
            UNIQUE(email)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expira_em TIMESTAMP NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            assunto TEXT,
            corpo TEXT,
            lida INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            acao TEXT NOT NULL,
            detalhes TEXT,
            ip TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inserir admin master se não existir
    cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    if not cursor.fetchone():
        # Senha: admin (hash)
        senha_hash = hashlib.sha256("admin".encode()).hexdigest()
        cursor.execute('''
            INSERT INTO usuarios (username, email, senha_hash, hierarquia)
            VALUES ('admin', 'admin@binpanel.com', ?, 1)
        ''', (senha_hash,))
    
    conn.commit()
    conn.close()

# Gerar hash de senha
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Verificar senha
def verify_password(password, hashed):
    return hash_password(password) == hashed

# Gerar tokens
def generate_tokens(user_id, empresa_id, hierarquia, username):
    # Token de acesso (30 minutos)
    access_token_data = {
        "user_id": user_id,
        "empresa_id": empresa_id,
        "hierarquia": hierarquia,
        "username": username,
        "exp": (datetime.utcnow() + timedelta(minutes=30)).timestamp(),
        "type": "access"
    }
    
    # Refresh token (7 dias)
    refresh_token_data = {
        "user_id": user_id,
        "exp": (datetime.utcnow() + timedelta(days=7)).timestamp(),
        "type": "refresh"
    }
    
    # Simples geração de token (em produção usar JWT)
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    
    # Salvar tokens no banco
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tokens (usuario_id, token, refresh_token, expira_em)
        VALUES (?, ?, ?, datetime('now', '+7 days'))
    ''', (user_id, access_token, refresh_token))
    conn.commit()
    conn.close()
    
    return access_token, refresh_token

# Verificar token
def verify_token(token):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.empresa_id, u.hierarquia, u.username 
        FROM tokens t
        JOIN usuarios u ON t.usuario_id = u.id
        WHERE t.token = ? AND t.expira_em > datetime('now') AND u.ativo = 1
    ''', (token,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "user_id": result[0],
            "empresa_id": result[1],
            "hierarquia": result[2],
            "username": result[3]
        }
    return None

# Handler HTTP
class BinPanelHandler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/static/'):
            self.serve_frontend()
        elif self.path.startswith('/api/'):
            self.handle_api_get()
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path.startswith('/api/'):
            self.handle_api_post()
        else:
            self.send_error(404)
    
    def serve_frontend(self):
        # Servir arquivos estáticos
        if self.path == '/':
            filepath = '../frontend/login.html'
        else:
            filepath = '../frontend' + self.path
        
        try:
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                
                # Determinar content-type
                if filepath.endswith('.html'):
                    self.send_header('Content-Type', 'text/html')
                elif filepath.endswith('.css'):
                    self.send_header('Content-Type', 'text/css')
                elif filepath.endswith('.js'):
                    self.send_header('Content-Type', 'application/javascript')
                elif filepath.endswith('.png'):
                    self.send_header('Content-Type', 'image/png')
                elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
                    self.send_header('Content-Type', 'image/jpeg')
                
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Erro ao servir arquivo: {e}")
            self.send_error(500)
    
    def handle_api_get(self):
        # Extrair token do header
        auth_header = self.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        
        user = None
        if token:
            user = verify_token(token)
        
        if self.path == '/api/auth/me':
            if user:
                self.send_json({
                    "id": user["user_id"],
                    "username": user["username"],
                    "empresa_id": user["empresa_id"],
                    "hierarquia": user["hierarquia"]
                })
            else:
                self.send_error(401)
        
        elif self.path.startswith('/api/empresas'):
            if user and user["hierarquia"] == 1:  # Apenas admin total
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM empresas ORDER BY nome")
                empresas = []
                for row in cursor.fetchall():
                    empresas.append({
                        "id": row[0],
                        "nome": row[1],
                        "dominio": row[2],
                        "ativo": bool(row[3]),
                        "config": json.loads(row[4]),
                        "criado_em": row[5]
                    })
                conn.close()
                self.send_json(empresas)
            else:
                self.send_error(403)
        
        elif self.path.startswith('/api/usuarios'):
            if user and user["hierarquia"] <= 2:  # Admin total ou empresa
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                
                if user["hierarquia"] == 1:  # Admin total
                    cursor.execute("SELECT * FROM usuarios ORDER BY hierarquia")
                else:  # Admin empresa
                    cursor.execute(
                        "SELECT * FROM usuarios WHERE empresa_id = ? ORDER BY hierarquia",
                        (user["empresa_id"],)
                    )
                
                usuarios = []
                for row in cursor.fetchall():
                    usuarios.append({
                        "id": row[0],
                        "empresa_id": row[1],
                        "username": row[2],
                        "email": row[3],
                        "hierarquia": row[5],
                        "cargo_personalizado": row[6],
                        "permissoes": json.loads(row[7]),
                        "ativo": bool(row[8]),
                        "criado_em": row[9]
                    })
                conn.close()
                self.send_json(usuarios)
            else:
                self.send_error(403)
        
        elif self.path.startswith('/api/emails'):
            if user:
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                
                # Buscar email do usuário
                cursor.execute("SELECT email FROM usuarios WHERE id = ?", (user["user_id"],))
                user_email = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT * FROM emails WHERE destinatario = ? ORDER BY criado_em DESC LIMIT 50",
                    (user_email,)
                )
                
                emails = []
                for row in cursor.fetchall():
                    emails.append({
                        "id": row[0],
                        "remetente": row[1],
                        "destinatario": row[2],
                        "assunto": row[3],
                        "corpo": row[4],
                        "lida": bool(row[5]),
                        "criado_em": row[6]
                    })
                conn.close()
                self.send_json(emails)
            else:
                self.send_error(401)
        
        else:
            self.send_error(404)
    
    def handle_api_post(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(post_data) if post_data else {}
        except:
            data = {}
        
        if self.path == '/api/auth/login':
            self.handle_login(data)
        
        elif self.path == '/api/auth/refresh':
            self.handle_refresh(data)
        
        elif self.path == '/api/usuarios':
            self.handle_create_usuario(data)
        
        elif self.path == '/api/empresas':
            self.handle_create_empresa(data)
        
        elif self.path == '/api/emails/send':
            self.handle_send_email(data)
        
        else:
            self.send_error(404)
    
    def handle_login(self, data):
        dominio = data.get('dominio', '').strip()
        username = data.get('username', '').strip()
        senha = data.get('senha', '').strip()
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Buscar empresa pelo domínio
        empresa_id = None
        if dominio and dominio != 'admin':
            cursor.execute("SELECT id FROM empresas WHERE dominio = ?", (dominio,))
            empresa = cursor.fetchone()
            if empresa:
                empresa_id = empresa[0]
            else:
                self.send_json_error("Domínio não encontrado", 401)
                conn.close()
                return
        
        # Buscar usuário
        if empresa_id:
            cursor.execute(
                "SELECT id, senha_hash, hierarquia, username FROM usuarios WHERE username = ? AND empresa_id = ?",
                (username, empresa_id)
            )
        else:
            # Admin master
            cursor.execute(
                "SELECT id, senha_hash, hierarquia, username FROM usuarios WHERE username = ? AND empresa_id IS NULL",
                (username,)
            )
        
        usuario = cursor.fetchone()
        conn.close()
        
        if not usuario:
            self.send_json_error("Credenciais inválidas", 401)
            return
        
        if not verify_password(senha, usuario[1]):
            self.send_json_error("Credenciais inválidas", 401)
            return
        
        # Gerar tokens
        access_token, refresh_token = generate_tokens(
            usuario[0], empresa_id, usuario[2], usuario[3]
        )
        
        self.send_json({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        })
    
    def handle_refresh(self, data):
        refresh_token = data.get('refresh_token', '')
        
        if not refresh_token:
            self.send_json_error("Refresh token requerido", 401)
            return
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.usuario_id, u.empresa_id, u.hierarquia, u.username
            FROM tokens t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE t.refresh_token = ? AND t.expira_em > datetime('now')
        ''', (refresh_token,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            self.send_json_error("Refresh token inválido", 401)
            return
        
        # Gerar novos tokens
        access_token, new_refresh_token = generate_tokens(
            result[0], result[1], result[2], result[3]
        )
        
        self.send_json({
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        })
    
    def handle_create_usuario(self, data):
        auth_header = self.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None
        
        user = verify_token(token) if token else None
        
        if not user or user["hierarquia"] > 2:
            self.send_json_error("Permissão negada", 403)
            return
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        senha = data.get('senha', '').strip()
        hierarquia = data.get('hierarquia', 7)
        
        if not username or not email or not senha:
            self.send_json_error("Dados incompletos", 400)
            return
        
        empresa_id = user["empresa_id"] if user["hierarquia"] > 1 else None
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            self.send_json_error("Email já cadastrado", 400)
            return
        
        # Hash da senha
        senha_hash = hash_password(senha)
        
        # Inserir usuário
        cursor.execute('''
            INSERT INTO usuarios (empresa_id, username, email, senha_hash, hierarquia)
            VALUES (?, ?, ?, ?, ?)
        ''', (empresa_id, username, email, senha_hash, hierarquia))
        
        usuario_id = cursor.lastrowid
        conn.commit()
        
        # Buscar usuário criado
        cursor.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        row = cursor.fetchone()
        conn.close()
        
        self.send_json({
            "id": row[0],
            "username": row[2],
            "email": row[3],
            "hierarquia": row[5],
            "empresa_id": row[1],
            "ativo": bool(row[8])
        })
    
    def handle_create_empresa(self, data):
        auth_header = self.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None
        
        user = verify_token(token) if token else None
        
        if not user or user["hierarquia"] != 1:
            self.send_json_error("Apenas admin total pode criar empresas", 403)
            return
        
        nome = data.get('nome', '').strip()
        dominio = data.get('dominio', '').strip()
        
        if not nome or not dominio:
            self.send_json_error("Dados incompletos", 400)
            return
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Verificar se domínio já existe
        cursor.execute("SELECT id FROM empresas WHERE dominio = ?", (dominio,))
        if cursor.fetchone():
            conn.close()
            self.send_json_error("Domínio já cadastrado", 400)
            return
        
        # Inserir empresa
        cursor.execute('''
            INSERT INTO empresas (nome, dominio) VALUES (?, ?)
        ''', (nome, dominio))
        
        empresa_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.send_json({
            "id": empresa_id,
            "nome": nome,
            "dominio": dominio,
            "ativo": True,
            "config": {}
        })
    
    def handle_send_email(self, data):
        auth_header = self.headers.get('Authorization', '')
        token = auth_header[7:] if auth_header.startswith('Bearer ') else None
        
        user = verify_token(token) if token else None
        
        if not user:
            self.send_json_error("Não autorizado", 401)
            return
        
        destinatario = data.get('destinatario', '').strip()
        assunto = data.get('assunto', '').strip()
        corpo = data.get('corpo', '').strip()
        
        if not destinatario or not assunto:
            self.send_json_error("Dados incompletos", 400)
            return
        
        # Buscar email do remetente
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM usuarios WHERE id = ?", (user["user_id"],))
        remetente_email = cursor.fetchone()[0]
        
        # Salvar email no banco
        cursor.execute('''
            INSERT INTO emails (remetente, destinatario, assunto, corpo)
            VALUES (?, ?, ?, ?)
        ''', (remetente_email, destinatario, assunto, corpo))
        
        conn.commit()
        conn.close()
        
        self.send_json({"message": "Email salvo com sucesso"})
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_json_error(self, message, code=400):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
    
    def log_message(self, format, *args):
        # Silenciar logs padrão
        pass

# Servidor de Email SMTP
class EmailHandler:
    def __init__(self):
        pass
    
    def handle_email(self, data):
        # Implementação simples de handler de email
        print(f"Email recebido: {data}")
        return True

def start_http_server():
    print(f"Iniciando BinPanel na porta {PORT}")
    print(f"Acesse: http://localhost:{PORT}")
    server = HTTPServer(('0.0.0.0', PORT), BinPanelHandler)
    server.serve_forever()

def main():
    # Inicializar banco de dados
    print("Inicializando banco de dados...")
    init_database()
    
    # Iniciar servidor HTTP
    start_http_server()

if __name__ == '__main__':
    main()