import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from aiosmtpd.controller import Controller
import database
import json

class BinPanelHandler:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not address.endswith('@binpanel.com'):
            return '550 Não aceitamos emails para este domínio'
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        print(f"Recebendo email de: {envelope.mail_from}")
        print(f"Para: {envelope.rcpt_tos}")
        print(f"Mensagem: {envelope.content.decode('utf-8', errors='replace')}")
        
        # Salvar no banco de dados
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            for destinatario in envelope.rcpt_tos:
                cursor.execute('''
                    INSERT INTO emails (remetente, destinatario, assunto, corpo)
                    VALUES (?, ?, ?, ?)
                ''', (
                    envelope.mail_from,
                    destinatario,
                    "Assunto não extraído",
                    envelope.content.decode('utf-8', errors='replace')
                ))
            conn.commit()
        
        return '250 Mensagem aceita'

def start_email_server():
    handler = BinPanelHandler()
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    controller.start()
    print(f"Servidor de email iniciado na porta 25")
    return controller

def send_email(to_email: str, subject: str, body: str, from_email: str = "noreply@binpanel.com"):
    try:
        # Configurar servidor SMTP (exemplo com Gmail)
        # Em produção, configure um servidor SMTP real
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        # Salvar no banco
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO emails (remetente, destinatario, assunto, corpo)
                VALUES (?, ?, ?, ?)
            ''', (from_email, to_email, subject, body))
            conn.commit()
        
        # Aqui você configuraria o servidor SMTP real
        # Por exemplo, para Gmail:
        # server = smtplib.SMTP('smtp.gmail.com', 587)
        # server.starttls()
        # server.login('seu-email@gmail.com', 'sua-senha')
        # server.send_message(msg)
        # server.quit()
        
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False