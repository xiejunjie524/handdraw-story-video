from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "one_click.py"
spec = importlib.util.spec_from_file_location("one_click", MODULE_PATH)
one_click = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(one_click)


class FakeResponse:
    def __init__(self, payload: dict | None = None, content: bytes = b"") -> None:
        self._payload = payload or {}
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class AtlasCloudConfigTests(TestCase):
    def test_resolved_image_config_uses_atlascloud_defaults(self) -> None:
        config = one_click.resolved_image_config({"provider": "atlas-cloud"})

        self.assertEqual(config["base_url"], "https://api.atlascloud.ai/api/v1")
        self.assertEqual(config["api_key_env"], "ATLASCLOUD_API_KEY")
        self.assertEqual(config["api_key_env_aliases"], ["ATLAS_CLOUD_API_KEY"])
        self.assertEqual(config["model"], "bytedance/seedream-v5.0-lite")

    def test_api_key_reads_aliases_in_order(self) -> None:
        config = {"api_key_env": "ATLASCLOUD_API_KEY", "api_key_env_aliases": ["ATLAS_CLOUD_API_KEY"]}
        with patch.dict(os.environ, {"ATLAS_CLOUD_API_KEY": "alias-key"}, clear=True):
            self.assertEqual(one_click.api_key(config, one_click.ATLASCLOUD_API_KEY_ENVS), "alias-key")

    def test_atlascloud_image_request_submits_polls_and_downloads(self) -> None:
        calls: list[tuple[str, dict | None]] = []

        def fake_post(url: str, **kwargs):
            calls.append((url, kwargs.get("json")))
            return FakeResponse({"code": 200, "data": {"id": "prediction-1", "status": "starting"}})

        def fake_get(url: str, **kwargs):
            if url.endswith("/model/prediction/prediction-1"):
                return FakeResponse({"code": 200, "data": {"status": "completed", "outputs": ["https://cdn.example/story.png"]}})
            if url == "https://cdn.example/story.png":
                return FakeResponse(content=b"png-bytes")
            raise AssertionError(f"unexpected URL: {url}")

        config = one_click.resolved_image_config({"provider": "atlascloud", "poll_interval": 0})
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "scene.png"
            with patch.dict(os.environ, {"ATLAS_CLOUD_API_KEY": "test-key"}, clear=True):
                with patch.object(one_click.requests, "post", side_effect=fake_post):
                    with patch.object(one_click.requests, "get", side_effect=fake_get):
                        one_click.image_request(config, "warm hand-drawn scene", output)

            self.assertEqual(output.read_bytes(), b"png-bytes")
            self.assertEqual(calls[0][0], "https://api.atlascloud.ai/api/v1/model/generateImage")
            self.assertEqual(calls[0][1]["model"], "bytedance/seedream-v5.0-lite")
            self.assertEqual(calls[0][1]["prompt"], "warm hand-drawn scene")
            self.assertEqual(calls[0][1]["image_size"], "1024x1024")

    def test_atlascloud_reference_images_are_uploaded(self) -> None:
        calls: list[tuple[str, dict | None]] = []

        def fake_post(url: str, **kwargs):
            if url.endswith("/model/uploadMedia"):
                return FakeResponse({"code": 200, "data": {"download_url": "https://cdn.example/ref.png"}})
            calls.append((url, kwargs.get("json")))
            return FakeResponse({"code": 200, "data": {"id": "prediction-2", "status": "starting"}})

        def fake_get(url: str, **kwargs):
            if url.endswith("/model/prediction/prediction-2"):
                return FakeResponse({"code": 200, "data": {"status": "completed", "outputs": ["https://cdn.example/out.png"]}})
            if url == "https://cdn.example/out.png":
                return FakeResponse(content=b"out-bytes")
            raise AssertionError(f"unexpected URL: {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            ref = Path(tmpdir) / "ref.png"
            ref.write_bytes(b"ref-bytes")
            output = Path(tmpdir) / "scene.png"
            config = one_click.resolved_image_config(
                {"provider": "atlascloud", "poll_interval": 0, "reference_images": [str(ref)]}
            )

            with patch.dict(os.environ, {"ATLASCLOUD_API_KEY": "test-key"}, clear=True):
                with patch.object(one_click.requests, "post", side_effect=fake_post):
                    with patch.object(one_click.requests, "get", side_effect=fake_get):
                        one_click.image_request(config, "same character, new pose", output)

            self.assertEqual(output.read_bytes(), b"out-bytes")
            self.assertEqual(calls[0][1]["image_url"], "https://cdn.example/ref.png")


if __name__ == "__main__":
    main()
