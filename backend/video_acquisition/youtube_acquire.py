"""Safe, reproducible acquisition of an explicitly authorized YouTube video."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse


class FailureCategory(StrEnum):
    JS_RUNTIME_MISSING = "JS_RUNTIME_MISSING"
    EJS_MISSING = "EJS_MISSING"
    HTTP_403 = "HTTP_403"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PO_TOKEN_REQUIRED = "PO_TOKEN_REQUIRED"
    MEDIA_UNAVAILABLE = "MEDIA_UNAVAILABLE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    DOWNLOAD_SUCCESS = "DOWNLOAD_SUCCESS"


class AcquisitionFailure(RuntimeError):
    """A categorized acquisition failure with a redacted diagnostic."""

    def __init__(self, category: FailureCategory, detail: str, manifest_path: Path):
        super().__init__(f"{category}: {detail}")
        self.category = category
        self.manifest_path = manifest_path


@dataclass(frozen=True)
class AcquisitionResult:
    media_path: Path
    manifest_path: Path
    video_id: str
    attempt: int
    sha256: str
    duration_seconds: float
    width: int
    height: int
    fps: float


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SENSITIVE = re.compile(
    r"(?i)(cookie|authorization|po[_ -]?token|visitor[_ -]?data|x-goog-[^:=\s]+)"
    r"([=:]\s*|%3D)[^\s&,'\"\\]+"
)


def _redact(value: str) -> str:
    return _SENSITIVE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        if not candidate and parsed.path.startswith("/embed/"):
            candidate = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else ""
    else:
        candidate = ""
    if not _VIDEO_ID.fullmatch(candidate):
        raise ValueError("source URL must be an explicit canonical YouTube video URL")
    return candidate


def _binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32":
        package_root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        candidates = sorted(package_root.glob(f"**/{name}.exe")) if package_root.exists() else []
        if candidates:
            return str(candidates[-1])
    return None


def _version(command: list[str]) -> str | None:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False, timeout=20).stdout.splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def _installed_ejs_version() -> str | None:
    try:
        return version("yt-dlp-ejs")
    except PackageNotFoundError:
        return None


def _alternative_client() -> str | None:
    """Use current yt-dlp's capability table instead of pinning a client name."""
    try:
        from yt_dlp.extractor.youtube import _base

        candidates = [
            name
            for name, settings in _base.INNERTUBE_CLIENTS.items()
            if settings.get("REQUIRE_JS_PLAYER") is False and settings.get("SUPPORTS_COOKIES") is False
        ]
        return sorted(candidates)[0] if candidates else None
    except (ImportError, AttributeError):
        return None


def _failure_category(log: str) -> FailureCategory:
    lower = log.lower()
    if "403" in lower or "forbidden" in lower:
        return FailureCategory.HTTP_403
    if "po token" in lower or "potoken" in lower:
        return FailureCategory.PO_TOKEN_REQUIRED
    if "sign in" in lower or "authentication" in lower or "cookies" in lower:
        return FailureCategory.AUTH_REQUIRED
    if "not available" in lower or "private video" in lower or "does not exist" in lower:
        return FailureCategory.MEDIA_UNAVAILABLE
    if "javascript runtime" in lower or "js runtime" in lower:
        return FailureCategory.JS_RUNTIME_MISSING
    if "yt-dlp-ejs" in lower or "external javascript" in lower:
        return FailureCategory.EJS_MISSING
    return FailureCategory.NETWORK_FAILURE


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ffprobe(path: Path, ffprobe: str) -> dict[str, object]:
    process = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if process.returncode:
        raise RuntimeError(_redact(process.stderr.strip() or "ffprobe failed"))
    metadata = json.loads(process.stdout)
    video = next((stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("ffprobe found no video stream")
    duration = float(metadata.get("format", {}).get("duration", 0))
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    numerator, _, denominator = str(video.get("avg_frame_rate", "0/1")).partition("/")
    fps = float(numerator) / float(denominator or 1)
    if duration <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("ffprobe returned invalid media dimensions or duration")
    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "container": metadata.get("format", {}).get("format_name"),
        "video_codec": video.get("codec_name"),
        "audio_codec": next(
            (stream.get("codec_name") for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"),
            None,
        ),
    }


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def acquire_youtube_video(
    source_url: str,
    destination: Path,
    *,
    use_chrome_cookies: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> AcquisitionResult:
    """Acquire exactly one authorized video URL; never discover related content."""
    video_id = _video_id(source_url)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    media_path = destination / f"{video_id}.mp4"
    manifest_path = destination / f"{video_id}.acquisition.json"
    logs_path = destination / f"{video_id}.yt-dlp.log"
    quarantine = destination / "quarantine"
    if media_path.exists():
        raise FileExistsError(f"refusing to overwrite existing acquisition for {video_id}")

    deno, ffprobe = _binary("deno"), _binary("ffprobe")
    ejs_version = _installed_ejs_version()
    if not deno:
        category, detail = FailureCategory.JS_RUNTIME_MISSING, "Deno runtime was not found"
    elif not ejs_version:
        category, detail = FailureCategory.EJS_MISSING, "yt-dlp-ejs package was not found"
    elif not ffprobe:
        category, detail = FailureCategory.NETWORK_FAILURE, "ffprobe is required to validate downloaded media"
    else:
        category = detail = None

    manifest: dict[str, object] = {
        "source_url": source_url,
        "video_id": video_id,
        "acquisition_utc": datetime.now(UTC).isoformat(),
        "yt_dlp_version": _version([sys.executable, "-m", "yt_dlp", "--version"]),
        "yt_dlp_ejs_version": ejs_version,
        "js_runtime": {"name": "deno", "version": _version([deno, "--version"]) if deno else None},
        "cookies_used": bool(use_chrome_cookies),
        "po_token_provider_used": False,
        "attempts": [],
    }
    if category:
        manifest.update({"status": category, "failure_detail": detail})
        _write_json(manifest_path, manifest)
        raise AcquisitionFailure(category, detail, manifest_path)

    template = str(destination / f"{video_id}.%(ext)s")
    attempts: list[tuple[int, str | None]] = [(1, None)]
    process_logs: list[str] = []
    for attempt, client in attempts:
        command = [
            sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "bv*+ba/b",
            "--merge-output-format", "mp4", "--js-runtimes", f"deno:{deno}",
            "--ffmpeg-location", str(Path(ffprobe).parent),
            "--no-progress", "--output", template,
        ]
        if client:
            command.extend(["--extractor-args", f"youtube:player_client={client}"])
        if use_chrome_cookies:
            command.extend(["--cookies-from-browser", "chrome"])
        command.append(source_url)
        process = runner(command, capture_output=True, text=True, check=False, timeout=900)
        output = _redact((process.stdout or "") + "\n" + (process.stderr or ""))
        process_logs.append(f"attempt={attempt} client={client or 'default'}\n{output}")
        manifest["attempts"].append({"number": attempt, "player_client": client or "default", "returncode": process.returncode})
        if process.returncode == 0 and media_path.is_file() and media_path.stat().st_size > 0:
            metadata = _ffprobe(media_path, ffprobe)
            manifest.update({
                "status": FailureCategory.DOWNLOAD_SUCCESS,
                "successful_attempt": attempt,
                "player_client": client or "default",
                "media": {
                    "path": media_path.name,
                    "bytes": media_path.stat().st_size,
                    "sha256": _sha256(media_path),
                    "format_ids": re.findall(r"Downloading \d+ format\(s\): ([^\r\n]+)", output),
                    **metadata,
                },
            })
            logs_path.write_text("\n\n".join(process_logs), encoding="utf-8")
            _write_json(manifest_path, manifest)
            return AcquisitionResult(
                media_path, manifest_path, video_id, attempt, str(manifest["media"]["sha256"]),
                float(metadata["duration_seconds"]), int(metadata["width"]), int(metadata["height"]), float(metadata["fps"]),
            )
        failure = _failure_category(output)
        if attempt == 1 and failure in {FailureCategory.HTTP_403, FailureCategory.PO_TOKEN_REQUIRED}:
            alternate = _alternative_client()
            if alternate:
                attempts.append((2, alternate))

    for partial in destination.glob(f"{video_id}.*"):
        if partial not in {manifest_path, logs_path} and partial.is_file():
            quarantine.mkdir(exist_ok=True)
            partial.replace(quarantine / partial.name)
    logs_path.write_text("\n\n".join(process_logs), encoding="utf-8")
    detail = _redact(process_logs[-1][-1500:]) if process_logs else "yt-dlp did not run"
    manifest.update({"status": failure, "failure_detail": detail})
    _write_json(manifest_path, manifest)
    raise AcquisitionFailure(failure, detail, manifest_path)
