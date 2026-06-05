"""Unit tests for app.services.image_utils (pure, no Docker/DB).

Runnable two ways:
  - pytest sentinel-api/tests/test_image_utils.py
  - python3 sentinel-api/tests/test_image_utils.py   (built-in fallback runner)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.image_utils import (  # noqa: E402
    apply_env_assignment,
    apply_image_tag,
    find_image_tag_env_vars,
    split_image_ref,
)

BACKEND = "ghcr.io/getpayd-tech/pandastarz-backend"


# ---------------------------------------------------------------------------
# split_image_ref
# ---------------------------------------------------------------------------

def test_split_tagless():
    assert split_image_ref(BACKEND) == (BACKEND, None)


def test_split_sha_tag():
    assert split_image_ref(f"{BACKEND}:63e5c52") == (BACKEND, "63e5c52")


def test_split_latest_tag():
    assert split_image_ref("ghcr.io/payd-labs/foo:latest") == ("ghcr.io/payd-labs/foo", "latest")


def test_split_suffixed_repo():
    assert split_image_ref("ghcr.io/org/repo-api:latest") == ("ghcr.io/org/repo-api", "latest")


def test_split_quoted():
    assert split_image_ref('"ghcr.io/org/repo:abc"') == ("ghcr.io/org/repo", "abc")
    assert split_image_ref("'ghcr.io/org/repo:abc'") == ("ghcr.io/org/repo", "abc")


def test_split_whitespace_padded():
    assert split_image_ref("  ghcr.io/org/repo:abc  ") == ("ghcr.io/org/repo", "abc")


def test_split_digest_is_tagless():
    assert split_image_ref("ghcr.io/org/repo@sha256:deadbeef") == ("ghcr.io/org/repo", None)


def test_split_registry_port_not_a_tag():
    assert split_image_ref("ghcr.io:443/org/repo:tag") == ("ghcr.io:443/org/repo", "tag")


def test_split_no_slash():
    assert split_image_ref("repo:tag") == ("repo", "tag")
    assert split_image_ref("repo") == ("repo", None)


# ---------------------------------------------------------------------------
# apply_image_tag
# ---------------------------------------------------------------------------

SINGLE = (
    'version: "3.8"\n'
    "\n"
    "services:\n"
    "  pandastarz-email-worker:\n"
    f"    image: {BACKEND}:OLDSHA\n"
    "    container_name: pandastarz-email-worker\n"
    "    restart: unless-stopped\n"
    "    env_file:\n"
    "      - .env\n"
    "    networks:\n"
    "      - proxy\n"
    "\n"
    "networks:\n"
    "  proxy:\n"
    "    external: true\n"
)


def test_single_service_only_image_line_changes():
    out, count = apply_image_tag(SINGLE, BACKEND, "NEWSHA")
    assert count == 1
    assert out == SINGLE.replace(f"{BACKEND}:OLDSHA", f"{BACKEND}:NEWSHA")
    # everything else byte-identical, trailing newline preserved
    assert out.endswith("    external: true\n")


def test_tagless_original_gets_tag():
    text = f"services:\n  app:\n    image: {BACKEND}\n"
    out, count = apply_image_tag(text, BACKEND, "abc")
    assert count == 1
    assert out == f"services:\n  app:\n    image: {BACKEND}:abc\n"


BLENDED = (
    "services:\n"
    "  acme-api:\n"
    "    image: ghcr.io/org/acme-api:latest\n"
    "    container_name: acme-api\n"
    "    restart: unless-stopped\n"
    "  acme-ui:\n"
    "    image: ghcr.io/org/acme-ui:latest\n"
    "    container_name: acme-ui\n"
    "    depends_on:\n"
    "      - acme-api\n"
    "\n"
    "networks:\n"
    "  proxy:\n"
    "    external: true\n"
)


def test_blended_both_images_bumped():
    out, count = apply_image_tag(BLENDED, "ghcr.io/org/acme", "SHA1")
    assert count == 2
    assert "    image: ghcr.io/org/acme-api:SHA1\n" in out
    assert "    image: ghcr.io/org/acme-ui:SHA1\n" in out
    # untouched structure
    assert "    depends_on:\n      - acme-api\n" in out
    assert out.endswith("    external: true\n")
    assert ":latest" not in out


def test_sidecars_untouched():
    text = (
        "services:\n"
        "  app:\n"
        "    image: ghcr.io/org/app:old\n"
        "  db:\n"
        "    image: postgres:16\n"
        "  cache:\n"
        "    image: redis:7\n"
    )
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 1
    assert "    image: ghcr.io/org/app:new\n" in out
    assert "    image: postgres:16\n" in out
    assert "    image: redis:7\n" in out


def test_quoted_image_line_preserves_quotes():
    text = '    image: "ghcr.io/org/app:old"\n'
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 1
    assert out == '    image: "ghcr.io/org/app:new"\n'


def test_inline_comment_and_spacing_preserved():
    text = "    image: ghcr.io/org/app:old   # pinned by sentinel\n"
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 1
    assert out == "    image: ghcr.io/org/app:new   # pinned by sentinel\n"


def test_digest_line_untouched():
    text = "    image: ghcr.io/org/app@sha256:deadbeefcafe\n"
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 0
    assert out == text


def test_no_image_lines_identity():
    text = "networks:\n  proxy:\n    external: true\n"
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 0
    assert out == text


def test_crlf_preserved():
    text = "services:\r\n  app:\r\n    image: ghcr.io/org/app:old\r\n"
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 1
    assert out == "services:\r\n  app:\r\n    image: ghcr.io/org/app:new\r\n"


def test_no_trailing_newline_preserved():
    text = "services:\n  app:\n    image: ghcr.io/org/app:old"
    out, count = apply_image_tag(text, "ghcr.io/org/app", "new")
    assert count == 1
    assert out == "services:\n  app:\n    image: ghcr.io/org/app:new"


def test_idempotent():
    once, c1 = apply_image_tag(SINGLE, BACKEND, "NEWSHA")
    twice, c2 = apply_image_tag(once, BACKEND, "NEWSHA")
    assert c1 == c2 == 1
    assert once == twice

    b1, bc1 = apply_image_tag(BLENDED, "ghcr.io/org/acme", "SHA1")
    b2, bc2 = apply_image_tag(b1, "ghcr.io/org/acme", "SHA1")
    assert bc1 == bc2 == 2
    assert b1 == b2


def test_base_does_not_substring_match_other_repo():
    # base 'ghcr.io/org/repo' must NOT match 'ghcr.io/org/repo2'
    text = "    image: ghcr.io/org/repo2:old\n"
    out, count = apply_image_tag(text, "ghcr.io/org/repo", "new")
    assert count == 0
    assert out == text


# ---------------------------------------------------------------------------
# custom compose image tag env vars
# ---------------------------------------------------------------------------

CUSTOM_MULTI_IMAGE = (
    "services:\n"
    "  api:\n"
    "    image: ${REGISTRY:-ghcr.io/org}/${PREFIX:-connect}-api:${CONNECT_IMAGE_TAG:-latest}\n"
    "  ui:\n"
    "    image: ${REGISTRY:-ghcr.io/org}/${PREFIX:-connect}-ui:${CONNECT_IMAGE_TAG:-latest}\n"
    "  worker:\n"
    "    image: ghcr.io/org/worker:${WORKER_IMAGE_TAG}\n"
    "  cache:\n"
    "    image: redis:7\n"
    "x-note: ${IGNORED_IMAGE_TAG:-latest}\n"
)


def test_find_image_tag_env_vars_from_image_lines_only():
    assert find_image_tag_env_vars(CUSTOM_MULTI_IMAGE) == [
        "CONNECT_IMAGE_TAG",
        "WORKER_IMAGE_TAG",
    ]


def test_apply_env_assignment_updates_existing_key():
    text = "# project env\nCONNECT_IMAGE_TAG=old\nOTHER=value\n"
    out, count = apply_env_assignment(text, "CONNECT_IMAGE_TAG", "new")
    assert count == 1
    assert out == "# project env\nCONNECT_IMAGE_TAG=new\nOTHER=value\n"


def test_apply_env_assignment_appends_missing_key_with_final_newline():
    text = "# project env\nOTHER=value"
    out, count = apply_env_assignment(text, "CONNECT_IMAGE_TAG", "new")
    assert count == 1
    assert out == "# project env\nOTHER=value\nCONNECT_IMAGE_TAG=new\n"


def test_apply_env_assignment_preserves_crlf():
    text = "OTHER=value\r\nCONNECT_IMAGE_TAG=old\r\n"
    out, count = apply_env_assignment(text, "CONNECT_IMAGE_TAG", "new")
    assert count == 1
    assert out == "OTHER=value\r\nCONNECT_IMAGE_TAG=new\r\n"


# ---------------------------------------------------------------------------
# Fallback runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fns = sorted(
        (n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)
    )
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e!r}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
