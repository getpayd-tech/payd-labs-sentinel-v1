from __future__ import annotations

import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel_cli import auth


def token_with_exp(expires_at: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expires_at}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeClient:
    response = FakeResponse({})
    calls: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def post(self, url: str, json: dict) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        return self.response


class SentinelCliAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.credentials_dir = Path(self.tmp.name) / ".sentinel"
        self.credentials_file = self.credentials_dir / "credentials.json"
        self.original_dir = auth.CREDENTIALS_DIR
        self.original_file = auth.CREDENTIALS_FILE
        auth.CREDENTIALS_DIR = self.credentials_dir
        auth.CREDENTIALS_FILE = self.credentials_file
        FakeClient.calls = []

    def tearDown(self) -> None:
        auth.CREDENTIALS_DIR = self.original_dir
        auth.CREDENTIALS_FILE = self.original_file
        self.tmp.cleanup()

    def write_credentials(self, refresh_token: str = "old-refresh") -> None:
        auth.save_credentials(token_with_exp(int(time.time()) - 30), refresh_token)

    def test_expired_token_refreshes_and_preserves_unrotated_refresh_token(self) -> None:
        self.write_credentials()
        fresh_access = token_with_exp(int(time.time()) + 600)
        FakeClient.response = FakeResponse({"authToken": fresh_access})

        with patch.object(auth.httpx, "Client", FakeClient):
            token = auth.get_valid_token("https://sentinel.paydlabs.com")

        self.assertEqual(token, fresh_access)
        self.assertEqual(
            FakeClient.calls,
            [{
                "url": "https://sentinel.paydlabs.com/api/v1/auth/refresh",
                "json": {"refresh_token": "old-refresh"},
            }],
        )
        stored = json.loads(self.credentials_file.read_text())
        self.assertEqual(stored["auth_token"], fresh_access)
        self.assertEqual(stored["refresh_token"], "old-refresh")

    def test_refresh_token_rotation_is_persisted(self) -> None:
        self.write_credentials()
        fresh_access = token_with_exp(int(time.time()) + 600)
        FakeClient.response = FakeResponse({
            "access_token": fresh_access,
            "refresh_token": "rotated-refresh",
        })

        with patch.object(auth.httpx, "Client", FakeClient):
            self.assertEqual(
                auth.get_valid_token("https://sentinel.paydlabs.com"),
                fresh_access,
            )

        stored = json.loads(self.credentials_file.read_text())
        self.assertEqual(stored["refresh_token"], "rotated-refresh")

    def test_expired_token_without_refresh_token_requires_login(self) -> None:
        auth.save_credentials(token_with_exp(int(time.time()) - 30), "")

        with patch.object(auth.httpx, "Client", FakeClient):
            self.assertIsNone(auth.get_valid_token("https://sentinel.paydlabs.com"))

        self.assertEqual(FakeClient.calls, [])

    def test_corrupt_credentials_require_login(self) -> None:
        self.credentials_dir.mkdir(parents=True)
        self.credentials_file.write_text("not-json")

        self.assertIsNone(auth.get_valid_token("https://sentinel.paydlabs.com"))


if __name__ == "__main__":
    unittest.main()
