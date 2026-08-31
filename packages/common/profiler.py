"""High-precision performance profiling, hardware discovery, and statistical measurement utilities."""

import ctypes
import os
import platform
import sys
import time
import tracemalloc
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class SystemHardwareSpecs:
    """Hardware and runtime platform specifications for benchmark provenance."""

    os_name: str
    os_release: str
    os_architecture: str
    cpu_processor: str
    logical_cores: int
    total_ram_gb: float
    python_version: str
    python_compiler: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_release": self.os_release,
            "os_architecture": self.os_architecture,
            "cpu_processor": self.cpu_processor,
            "logical_cores": self.logical_cores,
            "total_ram_gb": round(self.total_ram_gb, 2),
            "python_version": self.python_version,
            "python_compiler": self.python_compiler,
        }


def get_current_process_rss_mb() -> float:
    """Retrieve current process resident set size (RSS) in megabytes."""
    if sys.platform == "win32":
        try:

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            ):
                return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            pass

    # Fallback using tracemalloc peak
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        return peak / (1024.0 * 1024.0)

    return 0.0


def discover_system_hardware() -> SystemHardwareSpecs:
    """Discover local CPU, RAM, and OS specifications with cross-platform support."""
    os_name = platform.system()
    os_release = platform.release()
    os_arch = platform.machine()
    cpu_processor = platform.processor() or "Multi-Core CPU"
    cores = os.cpu_count() or 1
    total_ram_gb = 8.0

    if sys.platform == "win32":
        try:

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_ram_gb = stat.ullTotalPhys / (1024.0**3)
        except Exception:
            pass

    return SystemHardwareSpecs(
        os_name=os_name,
        os_release=os_release,
        os_architecture=os_arch,
        cpu_processor=cpu_processor,
        logical_cores=cores,
        total_ram_gb=total_ram_gb,
        python_version=platform.python_version(),
        python_compiler=platform.python_compiler(),
    )


@dataclass
class BenchmarkProfileResult:
    """Statistical measurement and resource profile of a benchmark run."""

    name: str
    total_items: int
    wall_clock_seconds: float
    throughput_items_per_sec: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    mean_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    std_latency_ms: float
    initial_rss_mb: float
    peak_rss_mb: float
    rss_delta_mb: float
    parallel_workers: int = 1
    speedup_vs_baseline: float = 1.0
    parallel_efficiency_pct: float = 100.0
    extra_metrics: dict[str, Any] = field(default_factory=dict)

    def print_summary(self) -> None:
        """Print formatted statistical summary table."""
        print(f"\n--- {self.name} Profile Results ---")
        print(f"  Items Processed      : {self.total_items:,}")
        print(f"  Wall-Clock Duration  : {self.wall_clock_seconds:.4f} s")
        print(f"  Throughput           : {self.throughput_items_per_sec:,.1f} items/sec")
        print(f"  P50 Latency          : {self.p50_latency_ms:.4f} ms")
        print(f"  P90 Latency          : {self.p90_latency_ms:.4f} ms")
        print(f"  P95 Latency          : {self.p95_latency_ms:.4f} ms")
        print(f"  P99 Latency          : {self.p99_latency_ms:.4f} ms")
        print(
            f"  Mean Latency         : {self.mean_latency_ms:.4f} ms (±{self.std_latency_ms:.4f} ms)"
        )
        print(
            f"  Min / Max Latency    : {self.min_latency_ms:.4f} ms / {self.max_latency_ms:.4f} ms"
        )
        print(
            f"  Initial / Peak RSS   : {self.initial_rss_mb:.1f} MB / {self.peak_rss_mb:.1f} MB (Delta: {self.rss_delta_mb:+.1f} MB)"
        )
        if self.parallel_workers > 1:
            print(
                f"  Parallel Speedup     : {self.speedup_vs_baseline:.2f}x on {self.parallel_workers} workers ({self.parallel_efficiency_pct:.1f}% efficiency)"
            )


class PerformanceProfiler:
    """High-precision execution timer and memory profiler with percentile stats."""

    def __init__(self, name: str, total_items: int = 1, parallel_workers: int = 1) -> None:
        self.name = name
        self.total_items = total_items
        self.parallel_workers = parallel_workers
        self.latencies_ms: list[float] = []
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._initial_rss: float = 0.0
        self._peak_rss: float = 0.0

    def start(self) -> "PerformanceProfiler":
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        self._initial_rss = get_current_process_rss_mb()
        self._peak_rss = self._initial_rss
        self._start_time = time.perf_counter()
        return self

    def record_item_latency(self, latency_ms: float) -> None:
        self.latencies_ms.append(latency_ms)
        curr_rss = get_current_process_rss_mb()
        if curr_rss > self._peak_rss:
            self._peak_rss = curr_rss

    def stop(
        self,
        speedup_vs_baseline: float = 1.0,
        extra_metrics: dict[str, Any] | None = None,
        wall_clock_seconds: float | None = None,
    ) -> BenchmarkProfileResult:
        self._end_time = time.perf_counter()
        wall_clock = (
            wall_clock_seconds
            if wall_clock_seconds is not None
            else (self._end_time - self._start_time)
        )
        curr_rss = get_current_process_rss_mb()
        if curr_rss > self._peak_rss:
            self._peak_rss = curr_rss

        if not self.latencies_ms:
            # If item latencies were not recorded individually, derive average from wall clock
            avg_item_ms = (wall_clock * 1000.0) / max(1, self.total_items)
            lats = [avg_item_ms]
        else:
            lats = self.latencies_ms

        arr = np.array(lats, dtype=np.float64)
        p50 = float(np.percentile(arr, 50))
        p90 = float(np.percentile(arr, 90))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        throughput = float(self.total_items) / max(0.00001, wall_clock)
        efficiency = (speedup_vs_baseline / max(1, self.parallel_workers)) * 100.0

        return BenchmarkProfileResult(
            name=self.name,
            total_items=self.total_items,
            wall_clock_seconds=wall_clock,
            throughput_items_per_sec=throughput,
            p50_latency_ms=p50,
            p90_latency_ms=p90,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            mean_latency_ms=mean,
            min_latency_ms=min_val,
            max_latency_ms=max_val,
            std_latency_ms=std,
            initial_rss_mb=self._initial_rss,
            peak_rss_mb=self._peak_rss,
            rss_delta_mb=self._peak_rss - self._initial_rss,
            parallel_workers=self.parallel_workers,
            speedup_vs_baseline=speedup_vs_baseline,
            parallel_efficiency_pct=efficiency,
            extra_metrics=extra_metrics or {},
        )


@contextmanager
def profile_section(
    name: str, total_items: int = 1, parallel_workers: int = 1
) -> Generator[PerformanceProfiler, None, None]:
    """Context manager for profiling a block of execution."""
    profiler = PerformanceProfiler(
        name=name, total_items=total_items, parallel_workers=parallel_workers
    ).start()
    try:
        yield profiler
    finally:
        pass
