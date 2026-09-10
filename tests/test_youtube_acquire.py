from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from backend.video_acquisition.youtube_acquire import (
    AcquisitionFailure,
    FailureCategory,
    _failure_category,
    _redact,
    _video_id,
    acquire_youtube_video,
)


URL = "https://youtu.be/P6UEdM5xy8M"


def test_authorized_url_parses_exact_video_id():
    assert _video_id(URL) == "P6UEdM5xy8M"
    with pytest.raises(ValueError):
        _video_id("https://www.youtube.com/results?search_query=anything")


def test_redaction_removes_sensitive_log_values():
    assert "secret" not in _redact("Cookie=secret Authorization: bearer-secret po_token=secret")
    assert "[REDACTED]" in _redact("Cookie=secret")


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("HTTP Error 403: Forbidden", FailureCategory.HTTP_403),
        ("Sign in to confirm your age", FailureCategory.AUTH_REQUIRED),
        ("PO Token is required", FailureCategory.PO_TOKEN_REQUIRED),
        ("This video is not available", FailureCategory.MEDIA_UNAVAILABLE),
        ("network is unreachable", FailureCategory.NETWORK_FAILURE),
    ],
)
def test_failure_categories(detail: str, expected: FailureCategory):
    assert _failure_category(detail) is expected


@pytest.mark.parametrize(
    ("runtime", "ejs_version", "expected"),
    [
        (None, "0.8.0", FailureCategory.JS_RUNTIME_MISSING),
        ("deno.exe", None, FailureCategory.EJS_MISSING),
    ],
)
def test_missing_runtime_dependencies_are_categorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: str | None, ejs_version: str | None, expected: FailureCategory
):
    import backend.video_acquisition.youtube_acquire as acquire

    monkeypatch.setattr(acquire, "_binary", lambda name: runtime if name == "deno" else "ffprobe.exe")
    monkeypatch.setattr(acquire, "_installed_ejs_version", lambda: ejs_version)
    monkeypatch.setattr(acquire, "_version", lambda command: "test-version")
    with pytest.raises(AcquisitionFailure) as error:
        acquire_youtube_video(URL, tmp_path)
    assert error.value.category is expected
    assert json.loads(error.value.manifest_path.read_text())["status"] == expected


def test_failed_download_writes_redacted_manifest_and_quarantines_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import backend.video_acquisition.youtube_acquire as acquire

    monkeypatch.setattr(acquire, "_binary", lambda name: "deno.exe" if name == "deno" else "ffprobe.exe")
    monkeypatch.setattr(acquire, "_installed_ejs_version", lambda: "0.8.0")
    monkeypatch.setattr(acquire, "_version", lambda command: "test-version")

    def failed_runner(command, **kwargs):
        (tmp_path / "P6UEdM5xy8M.part").write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1, "", "ERROR: HTTP Error 403: Cookie=secret")

    with pytest.raises(AcquisitionFailure) as error:
        acquire_youtube_video(URL, tmp_path, runner=failed_runner)
    assert error.value.category is FailureCategory.HTTP_403
    manifest = json.loads((tmp_path / "P6UEdM5xy8M.acquisition.json").read_text())
    assert manifest["status"] == FailureCategory.HTTP_403
    assert not (tmp_path / "P6UEdM5xy8M.part").exists()
    assert (tmp_path / "quarantine" / "P6UEdM5xy8M.part").exists()
    assert "secret" not in (tmp_path / "P6UEdM5xy8M.yt-dlp.log").read_text()


def test_refuses_to_overwrite_deterministic_destination(tmp_path: Path):
    (tmp_path / "P6UEdM5xy8M.mp4").write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        acquire_youtube_video(URL, tmp_path)


def test_success_uses_no_playlist_and_writes_safe_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import backend.video_acquisition.youtube_acquire as acquire

    monkeypatch.setattr(acquire, "_binary", lambda name: "deno.exe" if name == "deno" else "ffprobe.exe")
    monkeypatch.setattr(acquire, "_installed_ejs_version", lambda: "0.8.0")
    monkeypatch.setattr(acquire, "_version", lambda command: "test-version")
    monkeypatch.setattr(
        acquire,
        "_ffprobe",
        lambda path, binary: {
            "duration_seconds": 10.5,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "video_codec": "h264",
            "audio_codec": "aac",
        },
    )

    observed_command: list[str] = []

    def successful_runner(command, **kwargs):
        observed_command.extend(command)
        (tmp_path / "P6UEdM5xy8M.mp4").write_bytes(b"valid media bytes")
        return subprocess.CompletedProcess(command, 0, "downloaded", "")

    result = acquire_youtube_video(URL, tmp_path, runner=successful_runner)
    manifest = json.loads(result.manifest_path.read_text())
    assert "--no-playlist" in observed_command
    assert observed_command[observed_command.index("-f") + 1] == "bv*+ba/b"
    assert "--ffmpeg-location" in observed_command
    assert "--cookies-from-browser" not in observed_command
    assert manifest["status"] == FailureCategory.DOWNLOAD_SUCCESS
    assert manifest["source_url"] == URL
    assert manifest["media"]["duration_seconds"] == 10.5
