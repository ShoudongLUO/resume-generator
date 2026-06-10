from app.services.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    cipher = encrypt("my-secret-key-123")
    assert cipher != "my-secret-key-123"
    assert decrypt(cipher) == "my-secret-key-123"


def test_decrypt_garbage_raises():
    import pytest
    with pytest.raises(Exception):
        decrypt("not-a-valid-fernet-token")
