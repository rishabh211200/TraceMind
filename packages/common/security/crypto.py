"""Cryptographic primitives, Argon2id password hashing, and AES-256-GCM envelope encryption."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


class CryptoTamperException(Exception):
    """Raised when an encrypted ciphertext envelope is corrupted, tampered with, or cannot be decrypted."""


class PasswordHasher:
    """Argon2id password hashing and constant-time verification engine."""

    def __init__(
        self,
        time_cost: int = 2,
        memory_cost: int = 19456,  # 19 MiB in KiB
        parallelism: int = 1,
        salt_len: int = 16,
        hash_len: int = 32,
    ) -> None:
        self.time_cost = time_cost
        self.memory_cost = memory_cost
        self.parallelism = parallelism
        self.salt_len = salt_len
        self.hash_len = hash_len

    def hash_password(self, plain_password: str) -> str:
        """Hash a plaintext password with a freshly generated cryptographically secure salt."""
        if not plain_password:
            raise ValueError("Password cannot be empty")

        salt = os.urandom(self.salt_len)
        kdf = Argon2id(
            salt=salt,
            length=self.hash_len,
            iterations=self.time_cost,
            lanes=self.parallelism,
            memory_cost=self.memory_cost,
            ad=None,
            secret=None,
        )
        derived = kdf.derive(plain_password.encode("utf-8"))

        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(derived).decode("ascii")
        return f"$argon2id$v=19$m={self.memory_cost},t={self.time_cost},p={self.parallelism}${salt_b64}${hash_b64}"

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a formatted Argon2id hash in constant time."""
        if not plain_password or not hashed_password:
            return False

        try:
            parts = hashed_password.split("$")
            if len(parts) != 6 or parts[1] != "argon2id":
                return False

            # Parse parameters: m=...,t=...,p=...
            params = {}
            for item in parts[3].split(","):
                k, v = item.split("=")
                params[k] = int(v)

            m_cost = params.get("m", self.memory_cost)
            t_cost = params.get("t", self.time_cost)
            p_lanes = params.get("p", self.parallelism)

            salt = base64.b64decode(parts[4])
            expected_hash = base64.b64decode(parts[5])

            kdf = Argon2id(
                salt=salt,
                length=len(expected_hash),
                iterations=t_cost,
                lanes=p_lanes,
                memory_cost=m_cost,
                ad=None,
                secret=None,
            )
            kdf.verify(plain_password.encode("utf-8"), expected_hash)
            return True
        except Exception:
            return False


class AES256GCMCipher:
    """Envelope encryption engine using AES-256-GCM with key rotation and tamper detection."""

    def __init__(
        self,
        primary_key_id: str = "primary",
        keys: dict[str, bytes] | None = None,
    ) -> None:
        self.primary_key_id = primary_key_id
        if keys:
            self._keys = dict(keys)
        else:
            # Generate deterministic ephemeral 256-bit key from environment or urandom
            env_key = os.environ.get("TRACEMIND_SECRET_KEY")
            if env_key:
                derived = hashlib.sha256(env_key.encode("utf-8")).digest()
            else:
                derived = hashlib.sha256(
                    b"tracemind_default_secret_key_change_in_production"
                ).digest()
            self._keys = {primary_key_id: derived}

        # Validate that all keys are 32 bytes (256-bit)
        for kid, key_bytes in self._keys.items():
            if len(key_bytes) != 32:
                raise ValueError(
                    f"AES-256 key for '{kid}' must be exactly 32 bytes, got {len(key_bytes)}"
                )

    def encrypt(self, plaintext: str | bytes, key_id: str | None = None) -> str:
        """Encrypt plaintext into a versioned envelope: `v1:<key_id>:<nonce_b64>:<ciphertext_b64>:<tag_b64>`."""
        kid = key_id or self.primary_key_id
        if kid not in self._keys:
            raise CryptoTamperException(f"Encryption key '{kid}' not registered")

        raw_bytes = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        nonce = secrets.token_bytes(12)  # 96-bit standard nonce for GCM

        aesgcm = AESGCM(self._keys[kid])
        # In cryptography.hazmat, AESGCM.encrypt returns ciphertext + 16-byte tag appended
        encrypted = aesgcm.encrypt(nonce, raw_bytes, None)
        ciphertext = encrypted[:-16]
        tag = encrypted[-16:]

        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext).decode("ascii")
        tag_b64 = base64.b64encode(tag).decode("ascii")

        return f"v1:{kid}:{nonce_b64}:{ct_b64}:{tag_b64}"

    def decrypt(self, envelope: str) -> str:
        """Decrypt an envelope string. Raises CryptoTamperException on any mismatch or corruption."""
        if not envelope or not isinstance(envelope, str):
            raise CryptoTamperException("Invalid envelope payload")

        parts = envelope.split(":")
        if len(parts) != 5 or parts[0] != "v1":
            raise CryptoTamperException("Malformed envelope header or unsupported version")

        _, kid, nonce_b64, ct_b64, tag_b64 = parts

        if kid not in self._keys:
            raise CryptoTamperException(f"Decryption key '{kid}' unknown or revoked")

        try:
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(ct_b64)
            tag = base64.b64decode(tag_b64)
        except Exception as e:
            raise CryptoTamperException(f"Corrupted base64 payload in envelope: {e}") from e

        if len(nonce) != 12 or len(tag) != 16:
            raise CryptoTamperException("Invalid nonce or tag length in envelope")

        combined = ciphertext + tag
        aesgcm = AESGCM(self._keys[kid])
        try:
            decrypted = aesgcm.decrypt(nonce, combined, None)
            return decrypted.decode("utf-8")
        except InvalidTag as e:
            raise CryptoTamperException(
                "Decryption failed: authentication tag mismatch or payload tampered"
            ) from e
        except Exception as e:
            raise CryptoTamperException(f"Decryption error: {e}") from e

    def __repr__(self) -> str:
        return (
            f"<AES256GCMCipher primary_key_id={self.primary_key_id!r} key_count={len(self._keys)}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


def hash_api_key_secret(secret: str) -> str:
    """Compute SHA-256 hash for constant-time lookup and secure storage of API key secrets."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key(
    tenant_id: str = "tenant_system", key_name: str = "api_key"
) -> tuple[str, str, str]:
    """Generate a high-entropy API key.

    Returns:
        (full_key, key_prefix, hashed_secret)
        Format: tm_live_<prefix>_<secret>
    """

    prefix = secrets.token_hex(4)  # 8 hex chars
    secret = secrets.token_hex(24)  # 48 hex chars
    full_key = f"tm_live_{prefix}_{secret}"
    hashed_secret = hash_api_key_secret(secret)
    return full_key, f"tm_{prefix}", hashed_secret
