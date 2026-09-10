# YouTube video acquisition

`acquire_youtube_video(source_url, destination)` acquires exactly one explicitly
authorized YouTube video URL. It does not perform search, playlist traversal,
related-video/channel/comment retrieval, or identity inference.

The destination receives a deterministic `<video-id>.mp4`, a redacted
`<video-id>.yt-dlp.log`, and `<video-id>.acquisition.json`. Existing media or
manifests are never overwritten. Failed partial files are moved to
`quarantine/`. The manifest records non-secret provenance and validated media
properties, including SHA-256. Chrome cookies are used only if the caller
explicitly passes `use_chrome_cookies=True`; cookie values are neither retained
nor logged.

The primary attempt uses current `yt-dlp`, `yt-dlp-ejs`, Deno, and FFmpeg with
`--no-playlist -f bv*+ba/b --merge-output-format mp4`. After a 403 or PO-token
failure, the module dynamically reads the installed yt-dlp YouTube client
capability table to make one supported fallback attempt. It never creates,
scrapes, or stores PO tokens.
