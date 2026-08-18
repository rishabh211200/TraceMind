"""Deterministic statistical distributions and random variable sampling."""

import math
from typing import Any

import numpy as np

from apps.simulator.config import LatencyDistributionType


class DeterministicSampler:
    """Encapsulates a seeded NumPy random generator for fully reproducible sampling."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    @property
    def seed(self) -> int:
        """Active pseudo-random seed."""
        return self._seed

    def reseed(self, seed: int) -> None:
        """Reset RNG state with a new seed."""
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def sample_latency(
        self,
        baseline_ms: float,
        sigma: float = 0.35,
        distribution_type: LatencyDistributionType = LatencyDistributionType.LOGNORMAL,
        spike_probability: float = 0.02,
        spike_multiplier: float = 3.5,
    ) -> float:
        """Sample operation latency using heavy-tailed distributions with mean preservation."""
        baseline_ms = max(1.0, baseline_ms)

        if distribution_type == LatencyDistributionType.LOGNORMAL:
            # Mean-adjusted lognormal parameter mu = ln(mean) - 0.5 * sigma^2
            mu = math.log(baseline_ms) - 0.5 * (sigma**2)
            raw_latency = float(self._rng.lognormal(mean=mu, sigma=sigma))
        elif distribution_type == LatencyDistributionType.GAMMA:
            shape = 4.0
            scale = baseline_ms / shape
            raw_latency = float(self._rng.gamma(shape=shape, scale=scale))
        else:
            # Normal distribution truncated at 1.0ms
            raw_latency = max(
                1.0, float(self._rng.normal(loc=baseline_ms, scale=baseline_ms * sigma))
            )

        # Natural tail spike injection (e.g. GC pause / lock contention)
        if self._rng.uniform(0.0, 1.0) < spike_probability:
            raw_latency *= spike_multiplier

        return max(0.5, round(raw_latency, 2))

    def sample_bernoulli(self, probability: float) -> bool:
        """Sample binary boolean outcome with given true probability."""
        if probability <= 0.0:
            return False
        if probability >= 1.0:
            return True
        return bool(self._rng.uniform(0.0, 1.0) < probability)

    def sample_retry_backoff(self, base_backoff_ms: float, attempt: int) -> float:
        """Calculate exponential backoff with full jitter in milliseconds."""
        multiplier = 2**attempt
        max_backoff = base_backoff_ms * multiplier
        jitter = self.uniform(0.5, 1.5)
        return float(max(1.0, round(max_backoff * jitter, 2)))

    def sample_interarrival_ms(self, arrival_rate_per_sec: float) -> float:
        """Sample inter-arrival time in milliseconds for Poisson process."""
        arrival_rate_per_sec = max(0.001, arrival_rate_per_sec)
        # Exponential distribution with mean = 1 / lambda seconds = 1000 / lambda ms
        mean_interarrival_ms = 1000.0 / arrival_rate_per_sec
        interarrival = float(self._rng.exponential(scale=mean_interarrival_ms))
        return max(0.1, round(interarrival, 2))

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """Draw uniform random float in [low, high)."""
        u: float = float(self._rng.random())
        return low + (high - low) * u

    def choice(self, items: list[Any]) -> Any:
        """Pick an item uniformly from a non-empty sequence."""
        idx = int(self._rng.integers(0, len(items)))
        return items[idx]
