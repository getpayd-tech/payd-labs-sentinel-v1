"""Pure helpers for parsing image references and rewriting the ``image:``
line(s) of a docker-compose file in place.

No I/O, no DB, no Docker - kept import-light so it is trivially unit-testable.

Used by the deploy service so a tagged deploy actually moves the running
containers to the requested tag (instead of re-pulling the old pinned image).
"""
from __future__ import annotations

from pathlib import Path
import re

# image:  <optional-quote> <ref> <optional-quote>  <optional trailing comment>
# Matched against a single line with its EOL already stripped off.
_IMAGE_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)image:(?P<gap>[ \t]*)"
    r"(?P<quote>['\"]?)(?P<ref>[^'\"\s#]+)(?P=quote)"
    r"(?P<trailing>[ \t]*(?:#.*)?)$"
)
_IMAGE_TAG_ENV_RE = re.compile(
    r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*IMAGE_TAG)(?::-[^}]*)?\}"
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


def find_image_tag_env_vars(compose_text: str) -> list[str]:
    """Return tag env vars used by compose ``image:`` lines, in first-seen order.

    Custom multi-image compose stacks often express images as:

    ``image: ghcr.io/org/${IMAGE_PREFIX}-api:${IMAGE_TAG:-latest}``

    Those lines cannot be rewritten by ``apply_image_tag`` because the concrete
    image ref is resolved by Docker Compose. Sentinel can still apply the
    requested deployment tag by updating the referenced ``*IMAGE_TAG`` variable
    in the compose working directory's ``.env`` file.
    """
    seen: set[str] = set()
    names: list[str] = []

    for raw_line in compose_text.splitlines():
        if not raw_line.lstrip().startswith("image:"):
            continue
        for match in _IMAGE_TAG_ENV_RE.finditer(raw_line):
            name = match.group("name")
            if name in seen:
                continue
            seen.add(name)
            names.append(name)

    return names


def apply_env_assignment(env_text: str, key: str, value: str) -> tuple[str, int]:
    """Set one ``KEY=value`` assignment in dotenv text, appending if absent.

    Comments, unrelated lines, line endings, and missing final newlines are
    preserved. The returned count is ``1`` when the key was written.
    """
    out: list[str] = []
    updated = False

    for raw_line in env_text.splitlines(keepends=True):
        content = raw_line.splitlines()[0] if raw_line else raw_line
        eol = raw_line[len(content):]
        if content.startswith(f"{key}="):
            out.append(f"{key}={value}{eol}")
            updated = True
            continue
        out.append(raw_line)

    if updated:
        return "".join(out), 1

    prefix = "".join(out)
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += "\n"
    return f"{prefix}{key}={value}\n", 1


def compose_env_file_path(compose_file_path: str | Path) -> Path:
    """Return the implicit dotenv file Docker Compose reads for a compose file."""
    return Path(compose_file_path).parent / ".env"
