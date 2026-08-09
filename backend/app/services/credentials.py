from cryptography.fernet import Fernet
from app.core.config import settings

fernet = Fernet(settings.FERNET_KEY.encode())

def encrypt_payload(data: str) -> bytes:
    return fernet.encrypt(data.encode())

def decrypt_payload(payload_enc: bytes) -> str:
    return fernet.decrypt(payload_enc).decode()
