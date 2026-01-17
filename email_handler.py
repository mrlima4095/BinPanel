import asyncio
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import AsyncMessage
from email.parser import BytesParser
from email.policy import default
from database import get_db_connection
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailHandler(AsyncMessage):
    def __init__(self):
        super().__init__()
    
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
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
                envelope.rcpt_tos.append(address)
                logger.info(f"Email aceito para: {address}")
                return '250 OK'
            else:
                logger.warning(f"Domínio não encontrado: {domain}")
                return '550 Domínio não encontrado'
        except Exception as e:
            logger.error(f"Erro em handle_RCPT: {str(e)}")
            return '451 Erro temporário no servidor'
    
    async def handle_DATA(self, server, session, envelope):
        try:
            email_content = envelope.content.decode('utf-8', errors='ignore')
            msg = BytesParser(policy=default).parsebytes(envelope.content)
            
            sender = envelope.mail_from
            recipients = envelope.rcpt_tos
            
            logger.info(f"Email recebido de: {sender} para: {recipients}")
            
            for recipient in recipients:
                try:
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
                            ''', (sender, recipient, msg.get('subject', '(sem assunto)'), 
                                  email_content, domain_id))
                            
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

def start_email_server():
    """Inicia servidor SMTP"""
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

def start_email_server_async():
    """Versão assíncrona para rodar em thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    handler = EmailHandler()
    controller = Controller(
        handler, 
        hostname='0.0.0.0', 
        port=25,
        loop=loop
    )
    
    controller.start()
    logger.info(f"✅ Servidor de email iniciado na porta 25")
    
    try:
        loop.run_forever()
    except Exception as e:
        logger.error(f"Erro no loop do servidor de email: {str(e)}")