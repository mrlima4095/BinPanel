from flask import jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import bcrypt
from database import get_db_connection
from datetime import datetime

class Auth:
    @staticmethod
    def authenticate(username, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT u.*, d.domain_name, c.name as company_name 
        FROM users u 
        LEFT JOIN domains d ON u.domain_id = d.id 
        LEFT JOIN companies c ON u.company_id = c.id 
        WHERE u.username = ? AND u.status = 'active'
        ''', (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            # Atualizar último login
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                         (datetime.now(), user['id']))
            conn.commit()
            conn.close()
            
            user_dict = dict(user)
            user_dict.pop('password_hash', None)
            
            # Criar tokens
            access_token = create_access_token(identity={
                'id': user['id'],
                'username': user['username'],
                'is_domain_admin': user['is_domain_admin'],
                'is_super_admin': user['is_super_admin'],
                'domain_id': user['domain_id'],
                'company_id': user['company_id']
            })
            
            refresh_token = create_refresh_token(identity={
                'id': user['id'],
                'username': user['username']
            })
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user_dict
            }
        
        return None
    
    @staticmethod
    def refresh_token():
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user)
        return {'access_token': new_token}
    
    @staticmethod
    def has_permission(user_id, permission_name):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar permissões diretas do usuário
        cursor.execute('''
        SELECT COUNT(*) FROM user_permissions up
        JOIN permissions p ON up.permission_id = p.id
        WHERE up.user_id = ? AND p.name = ?
        ''', (user_id, permission_name))
        
        direct_permission = cursor.fetchone()[0] > 0
        
        if direct_permission:
            conn.close()
            return True
        
        # Verificar permissões via grupos
        cursor.execute('''
        SELECT COUNT(*) FROM user_groups ug
        JOIN group_permissions gp ON ug.group_id = gp.group_id
        JOIN permissions p ON gp.permission_id = p.id
        WHERE ug.user_id = ? AND p.name = ?
        ''', (user_id, permission_name))
        
        group_permission = cursor.fetchone()[0] > 0
        conn.close()
        
        return group_permission
    
    @staticmethod
    def is_domain_admin(user_id, domain_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_domain_admin, is_super_admin, domain_id FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user['is_super_admin']:
            return True
        
        if user['is_domain_admin']:
            if domain_id:
                return user['domain_id'] == domain_id
            return True
        
        return False