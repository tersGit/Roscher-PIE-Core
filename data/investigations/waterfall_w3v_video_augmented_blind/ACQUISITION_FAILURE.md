# Waterfall W3-V Video Acquisition Failure

**Status:** STOPPED_PRE_FREEZE  
**Ground truth:** NOT_STARTED  
**Recorded:** 2026-09-10T11:02:52Z

## Authorized source

| Field | Value |
|---|---|
| Supplied source URL | `https://youtu.be/P6UEdM5xy8M` |
| Supplied video ID | `P6UEdM5xy8M` |
| Source scope | Exact user-supplied URL only |
| Acquisition method | `python -m yt_dlp --no-playlist --no-write-info-json --no-write-thumbnail --no-write-description --no-write-comments -f "best[ext=mp4]/best"` |

## Result

The downloader did not acquire a video byte stream. YouTube returned
`HTTP Error 403: Forbidden` while downloading video data. yt-dlp also reported
that no supported JavaScript runtime was available, which can prevent access to
some YouTube formats.

| Required provenance field | Result |
|---|---|
| Original filename | Not available; no file acquired |
| SHA-256 | Not available; no file acquired |
| Duration | Not available; no file acquired |
| Resolution | Not available; no file acquired |
| FPS | Not available; no file acquired |
| Video/audio codec | Not available; no file acquired |

## Protocol stop

No fallback to W3-S occurred. No frames were extracted or selected, no W3-V
listing-only freeze was made, and no candidate imagery, ranking, comparison, or
Qwen transfer-package activity was performed. W3-S remains immutable and
unchanged, including listing-media freeze commit `fd4355e`, ranking checksum
`c1b9c8488d0e3a6873d4298e1edfa8e5fb96afb4659bd6c381194bc65ad3587d`, final
commits `0fa6df6` and `41858d0`, and the frozen 1,010-candidate W1 universe.
