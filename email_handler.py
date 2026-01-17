import asyncio
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope, Session
from email.parser import BytesParser
from email.policy import default
from database import get_db_connection
import logging
from typing import Optional, List

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailHandler:
    """Handler personalizado para processar emails"""
    
    async def handle_RCPT(self, server, session, envelope: Envelope, address: str, rcpt_options) -> str:
        """Valida destinatários"""
        try:
            if '@' not in address:
                return '550 Endereço inválido'
            
            domain = address.split('@')[-1].lower()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (domain,))
            domain_data = cursor.fetchone()
            conn.close()
            
            if domain_data:
                if not hasattr(envelope, 'rcpt_tos'):
                    envelope.rcpt_tos = []
                envelope.rcpt_tos.append(address)
                logger.info(f"Email aceito para: {address}")
                return '250 OK'
            else:
                logger.warning(f"Domínio não encontrado: {domain}")
                return '550 Domínio não encontrado'
        except Exception as e:
            logger.error(f"Erro em handle_RCPT: {str(e)}")
            return '451 Erro temporário no servidor'
    
    async def handle_DATA(self, server, session: Session, envelope: Envelope) -> str:
        """Processa dados do email"""
        try:
            email_content = envelope.content.decode('utf-8', errors='ignore')
            msg = BytesParser(policy=default).parsebytes(envelope.content)
            
            sender = envelope.mail_from
            recipients = getattr(envelope, 'rcpt_tos', [])
            
            logger.info(f"Email recebido de: {sender} para: {recipients}")
            
            for recipient in recipients:
                try:
                    if '@' not in recipient:
                        continue
                    
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
                            INSERT INTO emails (sender, recipient, subject, body, domain_id, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ''', (sender, recipient, msg.get('subject', '(sem assunto)'), 
                                  email_content, domain_id, 'received'))
                            
                            conn.commit()
                            logger.info(f"Email salvo para {recipient}")
                        else:
                            logger.warning(f"Usuário não encontrado: {recipient}")
                    
                    conn.close()
                    
                except Exception as e:
                    logger.error(f"Erro ao processar destinatário {recipient}: {str(e)}")
                    continue
            
            return '250 Message accepted for delivery'
            
        except Exception as e:
            logger.error(f"Erro em handle_DATA: {str(e)}")
            return '451 Erro temporário no processamento'
    
    async def handle_message(self, message):
        """Implementação do método abstrato - não usado no nosso caso"""
        return '250 OK'

def start_email_server():
    """Inicia servidor SMTP"""
    from aiosmtpd.controller import Controller
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    handler = EmailHandler()
    
    controller = Controller(
        handler, 
        hostname='0.0.0.0', 
        port=25,
        loop=loop
    )
    
    try:
        controller.start()
        logger.info(f"✅ Servidor de email iniciado na porta 25")
        
        # Manter o loop rodando
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("Parando servidor de email...")
    except Exception as e:
        logger.error(f"Erro no servidor de email: {str(e)}")
    finally:
        controller.stop()
        loop.close()