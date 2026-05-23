"""Utilitários de rede para a Biblioteca Pessoal."""

import socket

def obter_ip_local() -> str:
    """
    Descobre o IP local da máquina na rede atual.
    Tenta conectar a um host externo via UDP para que o sistema
    operacional revele a interface de rede ativa.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Não estabelece conexão real no UDP, apenas define a rota padrão.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
