"""Enterprise Security & Multi-Tenancy Cryptographic & Rate Limiter Benchmark Suite."""

import asyncio
import statistics
import time

from packages.common.security.crypto import (
    AES256GCMCipher,
    PasswordHasher,
)
from packages.common.security.jwt import JWTTokenManager
from packages.common.security.rate_limiter import InMemorySlidingWindowRateLimiter
from packages.domain.security import Permission, Role


def benchmark_aes256_gcm(iterations: int = 10_000) -> dict[str, float]:
    """Measure AES-256-GCM envelope encryption and decryption throughput."""
    cipher = AES256GCMCipher()
    sample_payload = '{"db_uri": "postgres://prod_admin:supersecret@10.0.1.50:5432/tracemind_enterprise", "tls": true}'

    # 1. Encryption benchmark
    start_enc = time.perf_counter()
    envelopes = [cipher.encrypt(sample_payload) for _ in range(iterations)]
    enc_duration = time.perf_counter() - start_enc
    enc_ops_sec = iterations / enc_duration
    enc_latency_us = (enc_duration / iterations) * 1_000_000

    # 2. Decryption benchmark
    start_dec = time.perf_counter()
    for env in envelopes:
        dec = cipher.decrypt(env)
        assert dec == sample_payload
    dec_duration = time.perf_counter() - start_dec
    dec_ops_sec = iterations / dec_duration
    dec_latency_us = (dec_duration / iterations) * 1_000_000

    return {
        "iterations": iterations,
        "encrypt_ops_per_sec": enc_ops_sec,
        "encrypt_latency_us": enc_latency_us,
        "decrypt_ops_per_sec": dec_ops_sec,
        "decrypt_latency_us": dec_latency_us,
    }


def benchmark_rs256_jwt(iterations: int = 2_000) -> dict[str, float]:
    """Measure RS256 token signing and verification throughput/latency."""
    jwt_mgr = JWTTokenManager()

    # 1. Token Creation (Signing)
    start_sign = time.perf_counter()
    tokens = [
        jwt_mgr.create_access_token(
            user_id=f"usr_{i}",
            tenant_id="tenant_perf",
            email="bench@tracemind.io",
            roles=[Role.OPERATOR],
            permissions=[Permission.WORKFLOWS_READ, Permission.REMEDIATION_EXECUTE],
        )
        for i in range(iterations)
    ]
    sign_duration = time.perf_counter() - start_sign
    sign_ops_sec = iterations / sign_duration
    sign_latency_ms = (sign_duration / iterations) * 1000

    # 2. Token Decoding & RS256 Asymmetric Verification
    latencies_ms: list[float] = []
    start_verify = time.perf_counter()
    for tok in tokens:
        t0 = time.perf_counter()
        payload = jwt_mgr.decode_and_verify(tok, expected_type="access")
        assert payload["sub"].startswith("usr_")
        latencies_ms.append((time.perf_counter() - t0) * 1000)
    verify_duration = time.perf_counter() - start_verify
    verify_ops_sec = iterations / verify_duration

    return {
        "iterations": iterations,
        "sign_ops_per_sec": sign_ops_sec,
        "sign_latency_ms": sign_latency_ms,
        "verify_ops_per_sec": verify_ops_sec,
        "verify_mean_latency_ms": statistics.mean(latencies_ms),
        "verify_p95_latency_ms": statistics.quantiles(latencies_ms, n=20)[18],
        "verify_p99_latency_ms": statistics.quantiles(latencies_ms, n=100)[98],
    }


async def benchmark_sliding_window_rate_limiter(iterations: int = 50_000) -> dict[str, float]:
    """Measure sliding-window rate limiter evaluation throughput."""
    limiter = InMemorySlidingWindowRateLimiter(default_rate_per_minute=1_000_000)
    keys = [f"tenant_bench_{i % 50}" for i in range(iterations)]

    start = time.perf_counter()
    for key in keys:
        res = await limiter.check(key, max_requests=1_000_000, window_seconds=60)
        assert res.allowed is True
    duration = time.perf_counter() - start
    ops_sec = iterations / duration
    latency_us = (duration / iterations) * 1_000_000

    return {
        "iterations": iterations,
        "ops_per_sec": ops_sec,
        "latency_us": latency_us,
    }


def benchmark_argon2id(iterations: int = 10) -> dict[str, float]:
    """Measure Argon2id password hashing and constant-time verification latency."""
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    passwords = [f"P@ssw0rdEnterprise2026_{i}!" for i in range(iterations)]

    # 1. Hashing
    start_hash = time.perf_counter()
    hashes = [hasher.hash_password(p) for p in passwords]
    hash_duration = time.perf_counter() - start_hash
    hash_latency_ms = (hash_duration / iterations) * 1000

    # 2. Verification
    start_ver = time.perf_counter()
    for p, h in zip(passwords, hashes, strict=True):
        valid = hasher.verify_password(p, h)
        assert valid is True
    ver_duration = time.perf_counter() - start_ver
    ver_latency_ms = (ver_duration / iterations) * 1000

    return {
        "iterations": iterations,
        "hash_latency_ms": hash_latency_ms,
        "verify_latency_ms": ver_latency_ms,
    }


async def run_all_benchmarks():
    print("=" * 80)
    print("TraceMind Enterprise Security & Multi-Tenancy Performance Benchmarks")
    print("=" * 80)

    # 1. AES-256-GCM
    print("\n[1/4] Running AES-256-GCM Envelope Encryption Benchmark...")
    aes_res = benchmark_aes256_gcm(iterations=10_000)
    print(f"  Iterations:          {aes_res['iterations']}")
    print(f"  Encrypt Throughput:  {aes_res['encrypt_ops_per_sec']:,.0f} ops/sec (latency: {aes_res['encrypt_latency_us']:.2f} µs)")
    print(f"  Decrypt Throughput:  {aes_res['decrypt_ops_per_sec']:,.0f} ops/sec (latency: {aes_res['decrypt_latency_us']:.2f} µs)")
    assert aes_res['decrypt_ops_per_sec'] >= 5_000, "AES-256-GCM throughput below 5,000 ops/s"

    # 2. RS256 JWT
    print("\n[2/4] Running RS256 JWT Token Signing & Verification Benchmark...")
    jwt_res = benchmark_rs256_jwt(iterations=2_000)
    print(f"  Iterations:          {jwt_res['iterations']}")
    print(f"  Sign Throughput:     {jwt_res['sign_ops_per_sec']:,.0f} ops/sec (latency: {jwt_res['sign_latency_ms']:.3f} ms)")
    print(f"  Verify Throughput:   {jwt_res['verify_ops_per_sec']:,.0f} ops/sec")
    print(f"  Verify Latency Mean: {jwt_res['verify_mean_latency_ms']:.4f} ms")
    print(f"  Verify Latency P95:  {jwt_res['verify_p95_latency_ms']:.4f} ms")
    print(f"  Verify Latency P99:  {jwt_res['verify_p99_latency_ms']:.4f} ms")
    assert jwt_res['verify_mean_latency_ms'] < 2.0, "RS256 verification mean latency exceeds 2.0ms"

    # 3. Sliding Window Rate Limiter
    print("\n[3/4] Running In-Memory Sliding-Window Rate Limiter Benchmark...")
    rl_res = await benchmark_sliding_window_rate_limiter(iterations=50_000)
    print(f"  Iterations:          {rl_res['iterations']}")
    print(f"  Throughput:          {rl_res['ops_per_sec']:,.0f} ops/sec (latency: {rl_res['latency_us']:.3f} µs)")
    assert rl_res['ops_per_sec'] >= 30_000, "Rate limiter throughput below 30,000 ops/s"

    # 4. Argon2id Password Hashing
    print("\n[4/4] Running Argon2id (m=19MiB, t=2, p=1) Password Hashing Benchmark...")
    argon_res = benchmark_argon2id(iterations=5)
    print(f"  Iterations:          {argon_res['iterations']}")
    print(f"  Hash Latency:        {argon_res['hash_latency_ms']:.2f} ms")
    print(f"  Verify Latency:      {argon_res['verify_latency_ms']:.2f} ms")

    print("\n" + "=" * 80)
    print("ALL SECURITY PERFORMANCE BENCHMARKS PASSED TARGET THRESHOLDS!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
