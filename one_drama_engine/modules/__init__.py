"""one_drama_engine.modules

Shared helpers for the localization / auto-dubbing pipeline plus lazy access to
the individual stage modules.

Submodules are exposed lazily (PEP 562) so that importing this package does not
drag in heavy optional dependencies such as ``torch``, ``demucs`` or
``whisper`` until the stage that needs them actually runs.

    from modules import audio_separator      # imports demucs machinery
    from modules import log, run_command     # cheap shared helpers
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence

__all__ = [
    # stage modules (lazy)
    "discovery",
    "downloader",
    "audio_separator",
    "transcriber",
    "translator",
    "tts_engine",
    "video_processor",
    "concatenator",
    "seo_generator",
    "drive_sync",
    "watermark_detector",
    "filler_trimmer",
    "channel_scout",
    "shorts_generator",
    # helpers
    "PipelineError",
    "MissingDependencyError",
    "log",
    "get_logger",
    "run_command",
    "require_binary",
    "ffprobe_duration",
    "ffprobe_has_audio",
    "ensure_dir",
    "safe_stem",
    "human_time",
    "srt_timestamp",
    "clamp",
    "chunked",
    "read_json",
    "write_json",
]

_LAZY_SUBMODULES = frozenset(
    {
        "discovery",
        "downloader",
        "audio_separator",
        "transcriber",
        "translator",
        "tts_engine",
        "video_processor",
        "concatenator",
        "seo_generator",
        "drive_sync",
        "watermark_detector",
        "filler_trimmer",
        "channel_scout",
        "shorts_generator",
    }
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class PipelineError(RuntimeError):
    """Any recoverable failure raised by a pipeline stage."""


class MissingDependencyError(PipelineError):
    """A required external binary or Python package is unavailable."""


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-16s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def get_logger(name: str = "one_drama") -> logging.Logger:
    """Return a configured logger, attaching a stderr handler exactly once."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("ONE_DRAMA_LOGLEVEL", "INFO").upper())
        logger.propagate = False
    return logger


log = get_logger()


# --------------------------------------------------------------------------- #
# Subprocess / binaries
# --------------------------------------------------------------------------- #
def require_binary(name: str, hint: str = "") -> str:
    """Return the absolute path to *name* or raise :class:`MissingDependencyError`."""
    path = shutil.which(name)
    if not path:
        message = f"Required executable '{name}' was not found on PATH."
        if hint:
            message += f" {hint}"
        raise MissingDependencyError(message)
    return path


def run_command(
    argv: Sequence[str],
    *,
    desc: str = "",
    capture: bool = True,
    check: bool = True,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run *argv* and return the completed process.

    Raises :class:`PipelineError` (never ``CalledProcessError``) so callers can
    handle every stage failure uniformly. ``stderr`` from the child process is
    truncated into the exception message, which is what makes FFmpeg problems
    debuggable without trawling through logs.
    """
    if not argv:
        raise PipelineError("run_command() received an empty argument list.")

    label = desc or os.path.basename(str(argv[0]))
    log.debug("exec: %s", " ".join(str(a) for a in argv))
    started = time.perf_counter()

    proc_env = dict(env if env is not None else os.environ)
    proc_env.pop("PYTHONHASHSEED", None)

    try:
        proc = subprocess.run(  # noqa: S603 - argv list, never shell=True
            [str(a) for a in argv],
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=proc_env,
        )
    except FileNotFoundError as exc:
        raise MissingDependencyError(f"{label}: executable not found ({exc}).") from exc
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"{label}: timed out after {timeout}s.") from exc

    elapsed = time.perf_counter() - started
    log.debug("%s finished rc=%s in %.1fs", label, proc.returncode, elapsed)

    if check and proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-25:]
        detail = "\n".join(tail) if tail else "(no output captured)"
        raise PipelineError(
            f"{label} failed with exit code {proc.returncode}:\n{detail}"
        )
    return proc


# --------------------------------------------------------------------------- #
# ffprobe helpers
# --------------------------------------------------------------------------- #
def ffprobe_duration(media_path: str) -> float:
    """Return the duration of *media_path* in seconds (0.0 when unknown)."""
    if not os.path.isfile(media_path):
        raise PipelineError(f"ffprobe: file does not exist: {media_path}")

    ffprobe = require_binary("ffprobe", "Install FFmpeg (ffprobe ships with it).")
    proc = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            media_path,
        ],
        desc="ffprobe(duration)",
        check=False,
    )
    raw = (proc.stdout or "").strip().splitlines()
    for line in raw:
        try:
            value = float(line.strip())
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    log.warning("ffprobe could not determine a duration for %s", media_path)
    return 0.0


def ffprobe_has_audio(media_path: str) -> bool:
    """Return ``True`` when *media_path* carries at least one audio stream."""
    ffprobe = require_binary("ffprobe")
    proc = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            media_path,
        ],
        desc="ffprobe(audio)",
        check=False,
    )
    return bool((proc.stdout or "").strip())


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def ensure_dir(path: str) -> str:
    """Create *path* (recursively) if needed and return it."""
    if path:
        os.makedirs(path, exist_ok=True)
    return path


def safe_stem(path: str) -> str:
    """Filename stem stripped of characters that upset shells and FFmpeg."""
    stem = os.path.splitext(os.path.basename(path))[0]
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in stem)
    return cleaned.strip("._") or "episode"


def clamp(value: float, low: float, high: float) -> float:
    """Constrain *value* to the inclusive ``[low, high]`` range."""
    if low > high:
        low, high = high, low
    return max(low, min(high, value))


def chunked(items: Sequence[Any], size: int) -> Iterable[list[Any]]:
    """Yield consecutive slices of *items* of at most *size* elements."""
    if size < 1:
        raise ValueError("chunk size must be >= 1")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def human_time(seconds: float) -> str:
    """Format *seconds* as ``H:MM:SS``."""
    seconds = max(0.0, float(seconds))
    hours, rem = divmod(int(round(seconds)), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def srt_timestamp(seconds: float) -> str:
    """Format *seconds* as an SRT timestamp (``HH:MM:SS,mmm``)."""
    seconds = max(0.0, float(seconds))
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def read_json(path: str, default: Any = None) -> Any:
    """Load JSON from *path*, returning *default* when missing or corrupt."""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read JSON %s (%s)", path, exc)
        return default


def write_json(path: str, payload: Any) -> str:
    """Atomically write *payload* as UTF-8 JSON to *path*."""
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


# --------------------------------------------------------------------------- #
# Lazy submodule access
# --------------------------------------------------------------------------- #
def __getattr__(name: str):  # pragma: no cover - import plumbing
    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:  # pragma: no cover - introspection helper
    return sorted(set(__all__) | set(globals()))
