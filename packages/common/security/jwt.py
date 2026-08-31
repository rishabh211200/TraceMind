"""Asymmetric RS256 JSON Web Token (JWT) manager with refresh rotation and revocation tracking."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Coroutine, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from packages.domain.security import AuthTokens, Permission, Role, User


class JWTException(Exception):
    """Base exception for JWT validation errors."""


class TokenExpiredException(JWTException):
    """Raised when a token's exp timestamp is in the past."""


class InvalidSignatureException(JWTException):
    """Raised when cryptographic signature verification fails."""


class TokenRevokedException(JWTException):
    """Raised when a token's JTI is in the revocation blocklist."""


class InvalidTokenException(JWTException):
    """Raised when token format, claims, or structure are malformed."""


def _b64url_encode(data: bytes) -> str:
    """Encode bytes into base64url format without trailing padding '='."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    """Decode base64url string with auto-padding."""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


class JWTTokenManager:
    """RS256 JWT Token lifecycle manager with in-memory revocation cache."""

    def __init__(
        self,
        private_key_pem: str | bytes | None = None,
        public_key_pem: str | bytes | None = None,
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        issuer: str = "tracemind-auth-service",
        revocation_checker: Callable[[str], Coroutine[Any, Any, bool]] | None = None,
    ) -> None:
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.issuer = issuer
        self.revocation_checker = revocation_checker
        self._in_memory_revoked_jtis: set[str] = set()

        if private_key_pem:
            raw_priv = (
                private_key_pem.encode("utf-8")
                if isinstance(private_key_pem, str)
                else private_key_pem
            )
            self._private_key = serialization.load_pem_private_key(raw_priv, password=None)
            if not isinstance(self._private_key, rsa.RSAPrivateKey):
                raise ValueError("Provided private key is not an RSA private key")
            self._public_key = self._private_key.public_key()
        else:
            # Generate 2048-bit RSA key pair dynamically
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            self._public_key = self._private_key.public_key()

        if public_key_pem and not private_key_pem:
            raw_pub = (
                public_key_pem.encode("utf-8")
                if isinstance(public_key_pem, str)
                else public_key_pem
            )
            pub_key = serialization.load_pem_public_key(raw_pub)
            if not isinstance(pub_key, rsa.RSAPublicKey):
                raise ValueError("Provided public key is not an RSA public key")
            self._public_key = pub_key

    def get_public_key_pem(self) -> str:
        """Export RSA public key in PEM format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def _sign_payload(self, payload: dict[str, Any]) -> str:
        """Encode and sign header and payload using RS256."""
        header = {"alg": "RS256", "typ": "JWT"}
        header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
        payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        h_b64 = _b64url_encode(header_json)
        p_b64 = _b64url_encode(payload_json)
        message = f"{h_b64}.{p_b64}".encode("ascii")

        signature = cast(rsa.RSAPrivateKey, self._private_key).sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        s_b64 = _b64url_encode(signature)
        return f"{h_b64}.{p_b64}.{s_b64}"

    def decode_and_verify(  # noqa: C901
        self,
        token: str,
        expected_type: str | None = None,
    ) -> dict[str, Any]:
        """Decode and verify RS256 signature, expiry, and revocation."""
        if not token or not isinstance(token, str):
            raise InvalidTokenException("Missing or invalid token string")

        parts = token.split(".")
        if len(parts) != 3:
            raise InvalidTokenException("Malformed JWT format: expected 3 dot-separated segments")

        h_b64, p_b64, s_b64 = parts
        message = f"{h_b64}.{p_b64}".encode("ascii")

        try:
            sig = _b64url_decode(s_b64)
        except Exception as e:
            raise InvalidTokenException(f"Invalid base64url signature encoding: {e}") from e

        # Cryptographic RS256 Verification
        try:
            self._public_key.verify(
                sig,
                message,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as e:
            raise InvalidSignatureException("RS256 JWT signature verification failed") from e
        except Exception as e:
            raise InvalidTokenException(f"Signature verification error: {e}") from e

        # Payload deserialization
        try:
            payload_bytes = _b64url_decode(p_b64)
            payload: dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            raise InvalidTokenException(f"Invalid JSON payload: {e}") from e

        # Expiration Check
        exp = payload.get("exp")
        if not exp:
            raise InvalidTokenException("Token missing 'exp' claim")

        current_ts = int(datetime.now(UTC).timestamp())
        if current_ts > exp:
            raise TokenExpiredException(f"Token expired at {exp}, current time {current_ts}")

        # Issuer Check
        if payload.get("iss") != self.issuer:
            raise InvalidTokenException(f"Token issuer mismatch: expected '{self.issuer}'")

        # Type Check
        token_type = payload.get("token_type")
        if expected_type and token_type != expected_type:
            raise InvalidTokenException(
                f"Token type mismatch: expected '{expected_type}', got '{token_type}'"
            )

        # Revocation Check (in-memory blocklist)
        jti = payload.get("jti")
        if jti and jti in self._in_memory_revoked_jtis:
            raise TokenRevokedException(f"Token JTI '{jti}' has been revoked")

        return payload

    async def verify_async(self, token: str, expected_type: str | None = None) -> dict[str, Any]:
        """Verify token with async database revocation check."""
        payload = self.decode_and_verify(token, expected_type=expected_type)
        jti = payload.get("jti")
        if jti and self.revocation_checker:
            is_revoked = await self.revocation_checker(jti)
            if is_revoked:
                self._in_memory_revoked_jtis.add(jti)
                raise TokenRevokedException(f"Token JTI '{jti}' has been revoked")
        return payload

    def revoke_jti(self, jti: str) -> None:
        """Add JTI to in-memory blocklist."""
        self._in_memory_revoked_jtis.add(jti)

    def is_jti_revoked(self, jti: str) -> bool:
        """Check if JTI is in in-memory blocklist."""
        return jti in self._in_memory_revoked_jtis

    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        roles: Sequence[Role | str],
        permissions: Sequence[Permission | str],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a signed 15-minute RS256 access token."""
        now = datetime.now(UTC)
        delta = expires_delta or timedelta(minutes=self.access_token_expire_minutes)
        exp = now + delta

        roles_str = [r.value if isinstance(r, Role) else str(r) for r in roles]
        perms_str = [p.value if isinstance(p, Permission) else str(p) for p in permissions]

        payload = {
            "iss": self.issuer,
            "sub": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "roles": roles_str,
            "permissions": perms_str,
            "token_type": "access",
            "jti": f"jti_acc_{uuid4().hex[:16]}",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return self._sign_payload(payload)

    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a signed 7-day RS256 refresh token."""
        now = datetime.now(UTC)
        delta = expires_delta or timedelta(days=self.refresh_token_expire_days)
        exp = now + delta

        payload = {
            "iss": self.issuer,
            "sub": user_id,
            "tenant_id": tenant_id,
            "token_type": "refresh",
            "jti": f"jti_ref_{uuid4().hex[:16]}",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return self._sign_payload(payload)

    def create_tokens_for_user(self, user: User) -> AuthTokens:
        """Create both access and refresh tokens for an authenticated user."""
        all_perms = user.get_all_permissions()
        access_token = self.create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            roles=user.roles,
            permissions=list(all_perms),
        )
        refresh_token = self.create_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_expire_minutes * 60,
            user_id=user.id,
            tenant_id=user.tenant_id,
            roles=[r.value if isinstance(r, Role) else str(r) for r in user.roles],
            permissions=[p.value if isinstance(p, Permission) else str(p) for p in all_perms],
        )

    def rotate_refresh_token(
        self,
        refresh_token: str,
        email: str = "user@tracemind.io",
        roles: Sequence[Role | str] | None = None,
        permissions: Sequence[Permission | str] | None = None,
    ) -> AuthTokens:
        """Atomically decode, revoke, and rotate a single-use refresh token into new token pair."""
        payload = self.decode_and_verify(refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        if jti:
            self.revoke_jti(jti)

        user_id = payload["sub"]
        tenant_id = payload["tenant_id"]
        assigned_roles = roles if roles is not None else [Role.VIEWER]
        assigned_perms = permissions if permissions is not None else []

        new_access_token = self.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            roles=assigned_roles,
            permissions=assigned_perms,
        )
        new_refresh_token = self.create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
        )

        return AuthTokens(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_expire_minutes * 60,
            user_id=user_id,
            tenant_id=tenant_id,
            roles=[r.value if isinstance(r, Role) else str(r) for r in assigned_roles],
            permissions=[p.value if isinstance(p, Permission) else str(p) for p in assigned_perms],
        )


# Global singleton instance
_jwt_manager: JWTTokenManager | None = None


def get_jwt_manager() -> JWTTokenManager:
    """Retrieve global JWTTokenManager singleton."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTTokenManager()
    return _jwt_manager
