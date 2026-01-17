#!/usr/bin/env python3
import subprocess
import sys
import time
import threading
from email_handler import start_email_server

def run_flask():
    subprocess.run([sys.executable, 'app.py'])

def run_email_server():
    controller = start_email_server()
    try:
        import asyncio
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()

if __name__ == '__main__':
    print("🚀 Iniciando Painel de Controle do Servidor...")
    
    # Iniciar servidor de email em thread separada
    email_thread = threading.Thread(target=run_email_server, daemon=True)
    email_thread.start()
    
    print("📧 Servidor de email iniciado na porta 25")
    time.sleep(2)
    
    # Iniciar servidor Flask
    print("🌐 Iniciando painel web na porta 8080...")
    run_flask()