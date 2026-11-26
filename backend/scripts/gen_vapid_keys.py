"""
Gera o par de chaves VAPID das notificações no celular (Web Push).

    python backend/scripts/gen_vapid_keys.py

Coloque as duas no servidor (Render → prospecta-api → Environment):
  VAPID_PUBLIC_KEY  = chave pública
  VAPID_PRIVATE_KEY = chave privada (segredo: nunca no repositório)
Trocar o par depois desliga as notificações dos aparelhos já cadastrados
(cada usuário precisa ativar de novo).
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
private = key.private_numbers().private_value.to_bytes(32, "big")
public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
print(f"VAPID_PUBLIC_KEY={b64u(public)}")
print(f"VAPID_PRIVATE_KEY={b64u(private)}")
