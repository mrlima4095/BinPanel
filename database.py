import sqlite3
import bcrypt
from datetime import datetime

def init_db():
    conn = sqlite3.connect('server_panel.db')
    cursor = conn.cursor()
    
    # Tabela de empresas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_email TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active'
    )
    ''')
    
    # Tabela de domínios
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain_name TEXT NOT NULL UNIQUE,
        company_id INTEGER,
        ssl_enabled BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )
    ''')
    
    # Tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        company_id INTEGER,
        domain_id INTEGER,
        is_domain_admin BOOLEAN DEFAULT 0,
        is_super_admin BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (company_id) REFERENCES companies (id),
        FOREIGN KEY (domain_id) REFERENCES domains (id)
    )
    ''')
    
    # Tabela de grupos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company_id INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )
    ''')
    
    # Tabela de permissões
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT
    )
    ''')
    
    # Tabela de associação usuário-grupo
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_groups (
        user_id INTEGER,
        group_id INTEGER,
        PRIMARY KEY (user_id, group_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (group_id) REFERENCES groups (id)
    )
    ''')
    
    # Tabela de associação grupo-permissão
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_permissions (
        group_id INTEGER,
        permission_id INTEGER,
        PRIMARY KEY (group_id, permission_id),
        FOREIGN KEY (group_id) REFERENCES groups (id),
        FOREIGN KEY (permission_id) REFERENCES permissions (id)
    )
    ''')
    
    # Tabela de associação usuário-permissão direta
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_permissions (
        user_id INTEGER,
        permission_id INTEGER,
        PRIMARY KEY (user_id, permission_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (permission_id) REFERENCES permissions (id)
    )
    ''')
    
    # Tabela de emails
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT,
        body TEXT,
        domain_id INTEGER,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'received',
        FOREIGN KEY (domain_id) REFERENCES domains (id)
    )
    ''')
    
    # Inserir permissões padrão
    default_permissions = [
        ('manage_domain', 'Gerenciar configurações do domínio'),
        ('manage_users', 'Gerenciar usuários do domínio'),
        ('manage_groups', 'Gerenciar grupos do domínio'),
        ('view_emails', 'Visualizar emails do domínio'),
        ('send_emails', 'Enviar emails pelo domínio'),
        ('manage_permissions', 'Gerenciar permissões'),
    ]
    
    cursor.executemany('INSERT OR IGNORE INTO permissions (name, description) VALUES (?, ?)', default_permissions)
    
    # Criar usuário super admin se não existir
    cursor.execute("SELECT * FROM users WHERE is_super_admin = 1")
    if not cursor.fetchone():
        password = "admin123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
        INSERT INTO users (username, email, password_hash, full_name, is_super_admin)
        VALUES (?, ?, ?, ?, ?)
        ''', ('superadmin', 'admin@system.local', password_hash, 'Super Administrador', 1))
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('server_panel.db')
    conn.row_factory = sqlite3.Row
    return conn