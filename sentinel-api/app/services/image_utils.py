"""Pure helpers for parsing image references and rewriting the ``image:``
line(s) of a docker-compose file in place.

No I/O, no DB, no Docker - kept import-light so it is trivially unit-testable.

Used by the deploy service so a tagged deploy actually moves the running
containers to the requested tag (instead of re-pulling the old pinned image).
"""
from __future__ import annotations

import re

# image:  <optional-quote> <ref> <optional-quote>  <optional trailing comment>
# Matched against a single line with its EOL already stripped off.
_IMAGE_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)image:(?P<gap>[ \t]*)"
    r"(?P<quote>['\"]?)(?P<ref>[^'\"\s#]+)(?P=quote)"
    r"(?P<trailing>[ \t]*(?:#.*)?)$"
)

# Digest-pinned references (``name@sha256:...``) are immutable by policy and
# are never rewritten.
DIGEST_MARKER = "@sha256:"


def split_image_ref(ref: str) -> tuple[str, str | None]:
    """Split an image reference into ``(name, tag)``.

    - Surrounding whitespace and one matching pair of quotes are stripped.
    - Digest form (``name@sha256:...``) returns ``(name, None)`` - digests are
      treated as tagless so callers leave them untouched.
    - The tag is only the part after the *last* ``:`` when that ``:`` comes
      after the last ``/`` (so a registry-port colon like ``host:5000/x`` is
      not mistaken for a tag).
    - ``-api`` / ``-ui`` suffixes need no special handling - they are part of
      the name.
    """
    ref = ref.strip()
    if len(ref) >= 2 and ref[0] in "\"'" and ref[-1] == ref[0]:
        ref = ref[1:-1]

    if "@" in ref:
        return ref.split("@", 1)[0], None

    slash = ref.rfind("/")
    colon = ref.rfind(":")
    if colon > slash and colon + 1 < len(ref):
        return ref[:colon], ref[colon + 1:]
    return ref, None


def apply_image_tag(compose_text: str, base_image: str, new_tag: str) -> tuple[str, int]:
    """Rewrite the tag of every ``image:`` line that belongs to this project.

    A line belongs to the project when its image name (tag stripped) is in the
    closed set ``{base_image, base_image-api, base_image-ui}``. That covers
    single-service projects (one match: ``name == base_image``) and blended
    two-image projects (``-api`` and ``-ui`` both bumped to the same tag, which
    is exactly what the blended CI guarantees). Sidecars (``postgres:16``,
    ``redis:7``, unrelated ``ghcr.io/...`` images) and digest-pinned lines are
    left untouched.

    Formatting is preserved exactly: indentation, the gap after ``image:``,
    original quoting, any inline ``# comment``, and the line ending (incl.
    CRLF and a missing final newline).

    Returns ``(new_text, count)`` where ``count`` is the number of lines
    rewritten.
    """
    targets = {base_image, f"{base_image}-api", f"{base_image}-ui"}
    out: list[str] = []
    count = 0

    for raw_line in compose_text.splitlines(keepends=True):
        content = raw_line.splitlines()[0] if raw_line else raw_line
        eol = raw_line[len(content):]

        m = _IMAGE_LINE_RE.match(content)
        if not m:
            out.append(raw_line)
            continue

        ref = m.group("ref")
        if "@" in ref:  # digest-pinned - immutable by policy
            out.append(raw_line)
            continue

        name, _tag = split_image_ref(ref)
        if name not in targets:
            out.append(raw_line)
            continue

        rebuilt = (
            f"{m.group('indent')}image:{m.group('gap')}"
            f"{m.group('quote')}{name}:{new_tag}{m.group('quote')}"
            f"{m.group('trailing')}"
        )
        out.append(rebuilt + eol)
        count += 1

    return "".join(out), count
