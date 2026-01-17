from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS
from config import Config
from database import init_db, get_db_connection
from auth import Auth
import json

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
jwt = JWTManager(app)

# Inicializar banco de dados
init_db()

# Rotas de autenticação
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Usuário e senha são obrigatórios'}), 400
    
    print(f"Tentativa de login: username={username}, password={'*' * len(password)}")
    
    auth_result = Auth.authenticate(username, password)
    
    if auth_result:
        print(f"Login bem-sucedido para: {username}")
        return jsonify(auth_result)
    
    print(f"Falha no login para: {username}")
    return jsonify({'error': 'Credenciais inválidas'}), 401

@app.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    return jsonify(Auth.refresh_token())

# Middleware para verificar permissões
def permission_required(permission_name):
    def decorator(f):
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user = get_jwt_identity()
            
            if not Auth.has_permission(current_user['id'], permission_name):
                return jsonify({'error': 'Permissão negada'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Rotas da API
@app.route('/api/domains', methods=['GET'])
@jwt_required()
def get_domains():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if current_user['is_super_admin']:
        cursor.execute('''
        SELECT d.*, c.name as company_name FROM domains d
        LEFT JOIN companies c ON d.company_id = c.id
        ''')
    else:
        cursor.execute('''
        SELECT d.*, c.name as company_name FROM domains d
        LEFT JOIN companies c ON d.company_id = c.id
        WHERE d.id = ? OR c.id = ?
        ''', (current_user['domain_id'], current_user['company_id']))
    
    domains = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(domain) for domain in domains])

@app.route('/api/domains', methods=['POST'])
@permission_required('manage_domain')
def create_domain():
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO domains (domain_name, company_id, ssl_enabled)
        VALUES (?, ?, ?)
        ''', (data['domain_name'], data.get('company_id'), data.get('ssl_enabled', False)))
        
        conn.commit()
        domain_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'message': 'Domínio criado com sucesso', 'id': domain_id}), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 400

@app.route('/api/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if current_user['is_super_admin']:
        cursor.execute('''
        SELECT u.*, d.domain_name, c.name as company_name FROM users u
        LEFT JOIN domains d ON u.domain_id = d.id
        LEFT JOIN companies c ON u.company_id = c.id
        ''')
    else:
        cursor.execute('''
        SELECT u.*, d.domain_name, c.name as company_name FROM users u
        LEFT JOIN domains d ON u.domain_id = d.id
        LEFT JOIN companies c ON u.company_id = c.id
        WHERE u.domain_id = ? OR u.company_id = ?
        ''', (current_user['domain_id'], current_user['company_id']))
    
    users = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(user) for user in users])

# Rotas do frontend
@app.route('/')
def index():
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
@jwt_required()
def dashboard():
    return render_template('dashboard.html')

@app.route('/domains')
@jwt_required()
def domains_page():
    return render_template('domains.html')

@app.route('/users')
@jwt_required()
def users_page():
    return render_template('users.html')

@app.route('/emails')
@jwt_required()
def emails_page():
    return render_template('emails.html')

@app.route('/settings')
@jwt_required()
def settings_page():
    return render_template('settings.html')

@app.route('/api/debug/users', methods=['GET'])
def debug_users():
    """Rota de debug para ver usuários (remover em produção)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, username, email, password_hash FROM users')
    users = cursor.fetchall()
    conn.close()
    
    result = []
    for user in users:
        result.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'password_hash': str(user['password_hash'])[:50] + '...'
        })
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=8080)