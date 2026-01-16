import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = "binpanel.db"

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela de empresas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS empresas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                dominio TEXT UNIQUE NOT NULL,
                ativo BOOLEAN DEFAULT 1,
                config TEXT DEFAULT '{}',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa_id INTEGER,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                senha_hash TEXT NOT NULL,
                hierarquia INTEGER DEFAULT 7, -- 1=Admin total, 7=Empregado
                cargo_personalizado TEXT,
                permissoes TEXT DEFAULT '[]',
                ativo BOOLEAN DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (empresa_id) REFERENCES empresas (id),
                UNIQUE(empresa_id, username),
                UNIQUE(email)
            )
        ''')
        
        # Tabela de logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                acao TEXT NOT NULL,
                detalhes TEXT,
                ip TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')
        
        # Tabela de tokens
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
        
        # Tabela de emails
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remetente TEXT NOT NULL,
                destinatario TEXT NOT NULL,
                assunto TEXT,
                corpo TEXT,
                lida BOOLEAN DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de hierarquias personalizadas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hierarquias_empresa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                nivel INTEGER NOT NULL,
                permissoes TEXT DEFAULT '[]',
                FOREIGN KEY (empresa_id) REFERENCES empresas (id)
            )
        ''')
        
        # Inserir admin master se não existir
        cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO usuarios (username, email, senha_hash, hierarquia)
                VALUES ('admin', 'admin@binpanel.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 1)
            ''')
        
        conn.commit()