#!/usr/bin/env python3
import subprocess
import sys
import time
import threading
import asyncio
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
        # Importar aqui para evitar problemas de importação circular
        from email_handler import start_email_server
        start_email_server()
    except Exception as e:
        logger.error(f"Erro no servidor de email: {str(e)}")

def check_port_25():
    """Verifica se podemos acessar a porta 25"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('0.0.0.0', 25))
        sock.close()
        return True
    except OSError:
        return False

def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 Iniciando Painel de Controle do Servidor")
    print("=" * 60)
    
    # Verificar porta 25
    if not check_port_25():
        logger.error("❌ Porta 25 não disponível. Execute como root ou configure permissões.")
        logger.error("   sudo setcap 'cap_net_bind_service=+ep' $(which python3)")
        return
    
    logger.info("✅ Porta 25 disponível")
    
    # Iniciar servidor de email em thread separada
    logger.info("📧 Iniciando servidor de email...")
    email_thread = threading.Thread(target=run_email_server, daemon=True, name="EmailServer")
    email_thread.start()
    
    # Aguardar inicialização
    time.sleep(3)
    
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