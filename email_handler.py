import asyncio
from aiosmtpd.controller import Controller
from email.parser import BytesParser
from email.policy import default
from database import get_db_connection
import re

class EmailHandler:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        # Verificar se o domínio do destinatário está registrado
        domain = address.split('@')[-1].lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (domain,))
        domain_data = cursor.fetchone()
        conn.close()
        
        if domain_data:
            envelope.rcpt_tos.append(address)
            return '250 OK'
        return '550 Domínio não encontrado'
    
    async def handle_DATA(self, server, session, envelope):
        # Processar email recebido
        email_content = envelope.content.decode('utf-8', errors='ignore')
        msg = BytesParser(policy=default).parsebytes(envelope.content)
        
        sender = envelope.mail_from
        recipients = envelope.rcpt_tos
        
        for recipient in recipients:
            username, domain = recipient.split('@')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Buscar domínio
            cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (domain,))
            domain_data = cursor.fetchone()
            
            if domain_data:
                domain_id = domain_data['id']
                
                # Buscar usuário pelo email
                cursor.execute('SELECT id FROM users WHERE email = ?', (recipient,))
                user_data = cursor.fetchone()
                
                if user_data:
                    # Salvar email no banco
                    cursor.execute('''
                    INSERT INTO emails (sender, recipient, subject, body, domain_id)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (sender, recipient, msg['subject'], email_content, domain_id))
                    
                    conn.commit()
            
            conn.close()
        
        return '250 Message accepted for delivery'

def start_email_server():
    handler = EmailHandler()
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    controller.start()
    print(f"Servidor de email iniciado na porta 25")
    return controller

if __name__ == '__main__':
    controller = start_email_server()
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()