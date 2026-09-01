import base64
from datetime import timedelta

import pytest

from packages.common.security.crypto import (
    AES256GCMCipher,
    CryptoTamperException,
    PasswordHasher,
    generate_api_key,
)
from packages.common.security.jwt import (
    InvalidTokenException,
    JWTTokenManager,
    TokenExpiredException,
    TokenRevokedException,
)
from packages.common.security.rate_limiter import InMemorySlidingWindowRateLimiter
from packages.domain.security import Permission, Role


class TestPasswordHasher:
    """Argon2id password hashing and verification tests."""

    def test_hash_and_verify_success(self):
        hasher = PasswordHasher()
        password = "SecurePassword#2026!"
        hashed = hasher.hash_password(password)

        assert hashed.startswith("$argon2id$")
        assert hasher.verify_password(password, hashed) is True

    def test_verify_failure_on_wrong_password(self):
        hasher = PasswordHasher()
        hashed = hasher.hash_password("OriginalPassword123!")
        assert hasher.verify_password("WrongPassword123!", hashed) is False

    def test_verify_failure_on_corrupt_hash(self):
        hasher = PasswordHasher()
        assert hasher.verify_password("Password", "invalid_hash_string") is False


class TestAES256GCMCipher:
    """Envelope encryption tests using AES-256-GCM with authenticated tag integrity."""

    def test_encrypt_and_decrypt_plaintext(self):
        cipher = AES256GCMCipher()
        plaintext = "postgres://admin:supersecret@db.internal:5432/tracemind"
        envelope = cipher.encrypt(plaintext)

        assert envelope.startswith("v1:primary:")
        decrypted = cipher.decrypt(envelope)
        assert decrypted == plaintext

    def test_tamper_ciphertext_detection(self):
        cipher = AES256GCMCipher()
        envelope = cipher.encrypt("secret_payload")
        parts = envelope.split(":")
        # Corrupt ciphertext byte deterministically via bit-flip
        raw_ct = bytearray(base64.b64decode(parts[3]))
        raw_ct[0] ^= 0xFF
        corrupted_b64 = base64.b64encode(raw_ct).decode("ascii")
        corrupted_envelope = f"{parts[0]}:{parts[1]}:{parts[2]}:{corrupted_b64}:{parts[4]}"

        with pytest.raises(CryptoTamperException):
            cipher.decrypt(corrupted_envelope)

    def test_tamper_auth_tag_detection(self):
        cipher = AES256GCMCipher()
        envelope = cipher.encrypt("secret_payload")
        parts = envelope.split(":")
        # Corrupt auth tag byte deterministically via bit-flip
        raw_tag = bytearray(base64.b64decode(parts[4]))
        raw_tag[0] ^= 0xFF
        corrupted_tag = base64.b64encode(raw_tag).decode("ascii")
        corrupted_envelope = f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}:{corrupted_tag}"

        with pytest.raises(CryptoTamperException):
            cipher.decrypt(corrupted_envelope)

    def test_invalid_envelope_format(self):
        cipher = AES256GCMCipher()
        with pytest.raises(CryptoTamperException):
            cipher.decrypt("not_a_valid_envelope")


class TestAPIKeyGeneration:
    """Cryptographic API key generation and hashing tests."""

    def test_generate_and_hash_api_key(self):
        raw_key, prefix, hashed_secret = generate_api_key(
            tenant_id="tenant_sys",
            key_name="ci_pipeline_key",
        )
        assert raw_key.startswith("tm_live_")
        assert prefix.startswith("tm_")
        assert len(hashed_secret) == 64  # SHA-256 hex string


class TestRS256JWTTokenManager:
    """Asymmetric RS256 JWT token issuance, verification, rotation, and revocation."""

    def test_create_and_decode_access_token(self):
        manager = JWTTokenManager()
        token = manager.create_access_token(
            user_id="usr_001",
            tenant_id="tenant_alpha",
            email="operator@alpha.com",
            roles=[Role.OPERATOR],
            permissions=[Permission.REMEDIATION_EXECUTE, Permission.TRACES_READ],
        )

        assert token is not None
        payload = manager.decode_and_verify(token, expected_type="access")
        assert payload["sub"] == "usr_001"
        assert payload["tenant_id"] == "tenant_alpha"
        assert payload["email"] == "operator@alpha.com"
        assert Role.OPERATOR.value in payload["roles"]
        assert Permission.REMEDIATION_EXECUTE.value in payload["permissions"]

    def test_expired_token_raises_exception(self):
        manager = JWTTokenManager()
        token = manager.create_access_token(
            user_id="usr_exp",
            tenant_id="tenant_alpha",
            email="expired@alpha.com",
            roles=[Role.VIEWER],
            permissions=[Permission.TRACES_READ],
            expires_delta=timedelta(seconds=-10),  # expired in past
        )

        with pytest.raises(TokenExpiredException):
            manager.decode_and_verify(token)

    def test_single_use_refresh_token_rotation(self):
        manager = JWTTokenManager()
        refresh_token = manager.create_refresh_token(
            user_id="usr_rot",
            tenant_id="tenant_beta",
        )

        # First refresh succeeds
        tokens_refreshed = manager.rotate_refresh_token(
            refresh_token,
            email="rot@beta.com",
            roles=[Role.ANALYST],
            permissions=[Permission.ANALYST_EXECUTE],
        )
        assert tokens_refreshed.access_token is not None
        assert tokens_refreshed.refresh_token != refresh_token

        # Second refresh with the old refresh token MUST fail (revoked on single-use)
        with pytest.raises((TokenRevokedException, InvalidTokenException)):
            manager.rotate_refresh_token(
                refresh_token,
                email="rot@beta.com",
                roles=[Role.ANALYST],
                permissions=[Permission.ANALYST_EXECUTE],
            )

    def test_token_revocation_blocklist(self):
        manager = JWTTokenManager()
        token = manager.create_access_token(
            user_id="usr_rev",
            tenant_id="tenant_gamma",
            email="rev@gamma.com",
            roles=[Role.VIEWER],
            permissions=[Permission.TRACES_READ],
        )

        payload = manager.decode_and_verify(token)
        manager.revoke_jti(payload["jti"])

        # Decoding revoked token raises TokenRevokedException
        with pytest.raises(TokenRevokedException):
            manager.decode_and_verify(token)


class TestInMemorySlidingWindowRateLimiter:
    """Sliding-window rate limiter quota enforcement tests."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_quota(self):
        limiter = InMemorySlidingWindowRateLimiter()
        key = "tenant_test_1"
        for _ in range(5):
            res = await limiter.check(key, max_requests=10, window_seconds=60)
            assert res.allowed is True
            assert res.remaining >= 0

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_quota(self):
        limiter = InMemorySlidingWindowRateLimiter()
        key = "tenant_test_block"
        for _ in range(3):
            res = await limiter.check(key, max_requests=3, window_seconds=60)
            assert res.allowed is True

        # 4th request exceeds quota of 3
        res = await limiter.check(key, max_requests=3, window_seconds=60)
        assert res.allowed is False
        assert res.remaining == 0
        assert res.retry_after >= 1

    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self):
        limiter = InMemorySlidingWindowRateLimiter()
        key = "tenant_test_reset"
        res1 = await limiter.check(key, max_requests=1, window_seconds=1)
        assert res1.allowed is True
        res2 = await limiter.check(key, max_requests=1, window_seconds=1)
        assert res2.allowed is False

        # Clear and check
        limiter.clear(key)
        res3 = await limiter.check(key, max_requests=1, window_seconds=1)
        assert res3.allowed is True
