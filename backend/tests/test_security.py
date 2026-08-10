from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_and_verify_roundtrip() -> None:
    stored = hash_password("secret-pass")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("secret-pass", stored)
    assert not verify_password("wrong", stored)


def test_verify_rejects_malformed() -> None:
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "bcrypt$salt$digest")


def test_jwt_roundtrip() -> None:
    token = create_access_token(user_id="u1", username="alice")
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["username"] == "alice"
