#!/usr/bin/env python3
import subprocess
import sys
import time
import threading
import asyncio
from email_handler import start_email_server_async
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_flask():
    """Executa o servidor Flask"""
    try:
        logger.info("🌐 Iniciando painel web na porta 5000...")
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        logger.info("Parando servidor web...")
    except Exception as e:
        logger.error(f"Erro no servidor Flask: {str(e)}")

def run_email_server():
    """Executa servidor de email em uma thread separada"""
    try:
        # Criar um loop de evento para esta thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from email_handler import EmailHandler
        from aiosmtpd.controller import Controller
        
        handler = EmailHandler()
        controller = Controller(handler, hostname='0.0.0.0', port=25)
        
        controller.start()
        logger.info("✅ Servidor de email iniciado na porta 25")
        
        # Manter a thread viva
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            controller.stop()
            loop.close()
            
    except Exception as e:
        logger.error(f"Erro no servidor de email: {str(e)}")

def check_prerequisites():
    """Verifica pré-requisitos"""
    import socket
    
    # Verificar se a porta 25 está disponível
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('0.0.0.0', 25))
        sock.close()
        logger.info("✅ Porta 25 disponível")
        return True
    except OSError as e:
        logger.error(f"❌ Porta 25 não disponível: {e}")
        logger.error("Execute como root ou configure permissões")
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 Iniciando Painel de Controle do Servidor")
    print("=" * 60)
    
    # Verificar pré-requisitos
    if not check_prerequisites():
        return
    
    # Iniciar servidor de email em thread separada
    logger.info("📧 Iniciando servidor de email...")
    email_thread = threading.Thread(target=run_email_server, daemon=True, name="EmailServer")
    email_thread.start()
    
    # Aguardar inicialização do servidor de email
    time.sleep(2)
    
    # Iniciar servidor Flask
    logger.info("🌐 Iniciando painel web...")
    
    try:
        run_flask()
    except KeyboardInterrupt:
        logger.info("\n🛑 Desligando servidor...")
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}")

if __name__ == '__main__':
    main()