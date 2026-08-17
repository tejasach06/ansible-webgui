from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


def generate_keypair(key_type: str, comment: str) -> tuple[str, str]:
    """Return (private_key_openssh_pem, public_key_openssh_line). Raises ValueError("bad_key_type")."""
    if key_type == "ed25519":
        key = ed25519.Ed25519PrivateKey.generate()
    elif key_type == "rsa4096":
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    else:
        raise ValueError("bad_key_type")

    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    if not private_pem.endswith("\n"):
        private_pem += "\n"

    public_openssh = key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode("utf-8")
    public_line = f"{public_openssh} {comment}"

    return private_pem, public_line
