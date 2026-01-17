import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import get_db_connection
import logging

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self):
        self.host = 'localhost'
        self.port = 2525  # Porta do PostMail
    
    def send_email(self, from_email, to_email, subject, body, html_body=None):
        """Envia email via PostMail"""
        try:
            # Verificar se o remetente tem permissão
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Extrair domínio do remetente
            sender_domain = from_email.split('@')[-1]
            
            cursor.execute('''
            SELECT d.id, u.id as user_id 
            FROM domains d
            LEFT JOIN users u ON u.email = ? AND u.domain_id = d.id
            WHERE d.domain_name = ?
            ''', (from_email, sender_domain))
            
            domain_data = cursor.fetchone()
            conn.close()
            
            if not domain_data:
                logger.error(f"Domínio não autorizado: {sender_domain}")
                return False
            
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Adicionar corpo texto
            msg.attach(MIMEText(body, 'plain'))
            
            # Adicionar corpo HTML se fornecido
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            # Enviar via PostMail
            with smtplib.SMTP(self.host, self.port) as server:
                # server.starttls()  # Descomente se usar TLS
                server.send_message(msg)
            
            logger.info(f"Email enviado de {from_email} para {to_email}")
            
            # Registrar no banco
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO emails (sender, recipient, subject, body, domain_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (from_email, to_email, subject, body, domain_data['id'], 'sent'))
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    def send_bulk_emails(self, from_email, recipients, subject, body, html_body=None):
        """Envia email para múltiplos destinatários"""
        results = []
        for recipient in recipients:
            success = self.send_email(from_email, recipient, subject, body, html_body)
            results.append({'recipient': recipient, 'success': success})
        
        return results