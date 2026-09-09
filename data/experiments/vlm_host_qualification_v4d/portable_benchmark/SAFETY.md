# Benchmark-only blind-directory safety guard

`portable_benchmark.py` is intentionally not integrated with production. It fail-closes before any control read:

1. Only a relative path exactly equal to a named item in `ALLOWED_CONTROLS` is accepted.
2. Glob metacharacters, absolute paths, `.`/`..`, forbidden IDs anywhere in the supplied text, duplicate manifest entries, and unsupported manifest fields are rejected.
3. Every component below the neutral root is checked for symlink or Windows junction status before canonicalization.
4. Canonicalization must remain inside the local `controls` root and end at a regular file.

No directory enumeration, recursive glob, or parent-tree scan is used as a safety check. The guard does not inspect a forbidden directory to decide whether it is forbidden.
