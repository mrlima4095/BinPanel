import click
import bcrypt
from database import get_db_connection

@click.group()
def cli():
    """Painel de Controle do Servidor - CLI"""
    pass

@cli.command()
@click.option('--domain', required=True, help='Nome do domínio')
@click.option('--company', required=True, help='Nome da empresa')
@click.option('--admin-email', required=True, help='Email do administrador')
@click.option('--admin-password', required=True, help='Senha do administrador')
def create_domain(domain, company, admin_email, admin_password):
    """Criar novo domínio com administrador"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Criar empresa
        cursor.execute('INSERT INTO companies (name, contact_email) VALUES (?, ?)', 
                      (company, admin_email))
        company_id = cursor.lastrowid
        
        # Criar domínio
        cursor.execute('INSERT INTO domains (domain_name, company_id) VALUES (?, ?)',
                      (domain, company_id))
        domain_id = cursor.lastrowid
        
        # Criar usuário administrador
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute('''
        INSERT INTO users (username, email, password_hash, full_name, 
                          company_id, domain_id, is_domain_admin)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (admin_email.split('@')[0], admin_email, password_hash, 
              f'Admin {company}', company_id, domain_id, 1))
        
        conn.commit()
        
        click.echo(f'✅ Domínio {domain} criado com sucesso!')
        click.echo(f'   Empresa: {company}')
        click.echo(f'   Admin: {admin_email}')
        
    except Exception as e:
        conn.rollback()
        click.echo(f'❌ Erro: {str(e)}')
    finally:
        conn.close()

@cli.command()
@click.option('--username', required=True, help='Nome de usuário')
@click.option('--email', required=True, help='Email do usuário')
@click.option('--password', required=True, help='Senha do usuário')
@click.option('--domain', required=True, help='Domínio do usuário')
@click.option('--full-name', help='Nome completo')
def create_user(username, email, password, domain, full_name):
    """Criar novo usuário"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Buscar domínio
        cursor.execute('SELECT id, company_id FROM domains WHERE domain_name = ?', (domain,))
        domain_data = cursor.fetchone()
        
        if not domain_data:
            click.echo(f'❌ Domínio {domain} não encontrado')
            return
        
        domain_id = domain_data['id']
        company_id = domain_data['company_id']
        
        # Criar usuário
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        cursor.execute('''
        INSERT INTO users (username, email, password_hash, full_name, 
                          company_id, domain_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, full_name or username, 
              company_id, domain_id))
        
        conn.commit()
        
        click.echo(f'✅ Usuário {username} criado com sucesso no domínio {domain}!')
        
    except Exception as e:
        conn.rollback()
        click.echo(f'❌ Erro: {str(e)}')
    finally:
        conn.close()

@cli.command()
@click.option('--domain', required=True, help='Domínio')
@click.option('--user', required=True, help='Nome de usuário')
@click.option('--permission', required=True, help='Nome da permissão')
def grant_permission(domain, user, permission):
    """Conceder permissão a usuário"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Buscar usuário e domínio
        cursor.execute('''
        SELECT u.id, u.domain_id FROM users u
        JOIN domains d ON u.domain_id = d.id
        WHERE u.username = ? AND d.domain_name = ?
        ''', (user, domain))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            click.echo(f'❌ Usuário {user} não encontrado no domínio {domain}')
            return
        
        # Buscar permissão
        cursor.execute('SELECT id FROM permissions WHERE name = ?', (permission,))
        permission_data = cursor.fetchone()
        
        if not permission_data:
            click.echo(f'❌ Permissão {permission} não encontrada')
            return
        
        # Conceder permissão
        cursor.execute('''
        INSERT OR IGNORE INTO user_permissions (user_id, permission_id)
        VALUES (?, ?)
        ''', (user_data['id'], permission_data['id']))
        
        conn.commit()
        
        click.echo(f'✅ Permissão {permission} concedida a {user} no domínio {domain}!')
        
    except Exception as e:
        conn.rollback()
        click.echo(f'❌ Erro: {str(e)}')
    finally:
        conn.close()

@cli.command()
def list_domains():
    """Listar todos os domínios"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT d.domain_name, c.name as company, COUNT(u.id) as users
    FROM domains d
    LEFT JOIN companies c ON d.company_id = c.id
    LEFT JOIN users u ON d.id = u.domain_id
    GROUP BY d.id
    ''')
    
    domains = cursor.fetchall()
    
    click.echo("📋 Domínios Registrados:")
    click.echo("-" * 60)
    
    for domain in domains:
        click.echo(f"🌐 Domínio: {domain['domain_name']}")
        click.echo(f"   Empresa: {domain['company']}")
        click.echo(f"   Usuários: {domain['users']}")
        click.echo()
    
    conn.close()

if __name__ == '__main__':
    cli()