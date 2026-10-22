import hashlib
import hmac


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if signature is None:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # compare_digest не даёт судить по времени ответа, на каком символе расхождение
    return hmac.compare_digest(expected.encode(), signature.encode())
