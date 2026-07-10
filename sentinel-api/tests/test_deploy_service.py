"""Unit tests for Sentinel deployment service helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app.services.deploy_service import _parse_compose_config_json  # noqa: E402


def test_parse_compose_config_json_accepts_clean_json():
    rendered, warning = _parse_compose_config_json('{"services":{"api":{"image":"fixture:abc"}}}')

    assert rendered["services"]["api"]["image"] == "fixture:abc"
    assert warning is None


def test_parse_compose_config_json_ignores_compose_warning_prefix():
    rendered, warning = _parse_compose_config_json(
        'time="2026-07-10T15:21:27Z" level=warning '
        'msg="/apps/fixture/docker-compose.yml: the attribute `version` is obsolete"\n'
        '{"name":"fixture","services":{"api":{"image":"fixture:abc"}}}'
    )

    assert rendered["name"] == "fixture"
    assert rendered["services"]["api"]["image"] == "fixture:abc"
    assert "attribute `version` is obsolete" in warning


def test_parse_compose_config_json_rejects_output_without_json():
    with pytest.raises(ValueError):
        _parse_compose_config_json("docker compose failed before rendering")
