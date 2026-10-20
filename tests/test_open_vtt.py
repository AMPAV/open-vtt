import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
import wave


MODULE_PATH = Path(__file__).parents[1] / "open-vtt.py"
SPEC = importlib.util.spec_from_file_location("open_vtt", MODULE_PATH)
open_vtt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(open_vtt)


class FakeModels:
    def __init__(self):
        self.request = None

    def generate_content(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            text="preface\nWEBVTT\n\n00:00:00.000 --> 00:00:01.000\nTest\n```",
            usage_metadata=None,
        )


class FakeFiles:
    def __init__(self):
        self.uploaded = None

    def upload(self, *, file):
        self.uploaded = file
        return SimpleNamespace(
            name="files/test",
            uri="https://generativelanguage.googleapis.com/files/test",
            mime_type="audio/mp4",
            state=SimpleNamespace(name="ACTIVE"),
        )


class FakeClient:
    def __init__(self):
        self.models = FakeModels()
        self.files = FakeFiles()
        self.closed = False

    def close(self):
        self.closed = True


class FakeBlob:
    def __init__(self, storage, bucket, name):
        self.storage = storage
        self.bucket = bucket
        self.name = name

    def upload_from_filename(self, filename, *, content_type):
        self.storage.uploads.append((filename, self.bucket, self.name, content_type))

    def delete(self):
        self.storage.deleted.append((self.bucket, self.name))


class FakeBucket:
    def __init__(self, storage, name):
        self.storage = storage
        self.name = name

    def blob(self, name):
        return FakeBlob(self.storage, self.name, name)


class FakeStorage:
    def __init__(self):
        self.uploads = []
        self.deleted = []

    def bucket(self, name):
        return FakeBucket(self, name)


class OpenVttAuthTests(unittest.TestCase):
    def test_auto_backend_prefers_api_key_and_falls_back_to_vertex(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(open_vtt.resolve_gemini_backend("test-key"), "developer")
            self.assertEqual(open_vtt.resolve_gemini_backend(None), "vertex")

    def test_create_clients_use_backend_specific_auth(self):
        with mock.patch.object(open_vtt.genai, "Client") as client_class:
            open_vtt.create_gemini_client("developer", "test-key")
        client_class.assert_called_once_with(api_key="test-key")

        with mock.patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "GOOGLE_CLOUD_LOCATION": "test-location",
            },
        ), mock.patch.object(open_vtt.genai, "Client") as client_class:
            open_vtt.create_gemini_client("vertex")
        client_class.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="test-location",
        )

    def _paths(self, root):
        prompt = root / "prompt.md"
        subtitles = root / "subtitles.vtt"
        media = root / "sample.m4a"
        prompt.write_text("Analyze at {{THINKING_LEVEL}} effort.", encoding="utf-8")
        subtitles.write_text("WEBVTT\n", encoding="utf-8")
        media.write_bytes(b"media-bytes")
        return prompt, subtitles, media

    def test_developer_backend_uses_files_api(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory:
            prompt, subtitles, media = self._paths(Path(directory))
            result = open_vtt.call_gemini(
                prompt,
                subtitles,
                media,
                client=client,
                backend="developer",
                api_key="test-key",
            )

        self.assertEqual(result["vtt"], "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nTest")
        self.assertEqual(client.files.uploaded, media)
        self.assertEqual(client.models.request["model"], "gemini-3.1-pro-preview")
        media_part, prompt_text = client.models.request["contents"]
        self.assertEqual(media_part.file_data.mime_type, "audio/mp4")
        self.assertIn("Analyze at HIGH effort.", prompt_text)

    def test_vertex_backend_stages_to_gcs_and_cleans_up(self):
        client = FakeClient()
        storage = FakeStorage()
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"OPEN_VTT_GCS_BUCKET": "gs://test-bucket"},
        ):
            prompt, subtitles, media = self._paths(Path(directory))
            result = open_vtt.call_gemini(
                prompt,
                subtitles,
                media,
                client=client,
                storage_client=storage,
                backend="vertex",
            )

        self.assertIsNotNone(result)
        self.assertEqual(len(storage.uploads), 1)
        self.assertEqual(len(storage.deleted), 1)
        self.assertEqual(storage.uploads[0][1], "test-bucket")
        self.assertEqual(storage.deleted[0], storage.uploads[0][1:3])
        media_part = client.models.request["contents"][0]
        self.assertTrue(media_part.file_data.file_uri.startswith("gs://test-bucket/"))

    def test_vertex_backend_uses_inline_media_without_bucket(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {"OPEN_VTT_GCS_BUCKET": ""},
            clear=False,
        ), mock.patch.dict(open_vtt.CONFIG["gemini"], {"gcs_bucket": None}):
            prompt, subtitles, media = self._paths(Path(directory))
            result = open_vtt.call_gemini(
                prompt,
                subtitles,
                media,
                client=client,
                backend="vertex",
            )

        self.assertIsNotNone(result)
        media_part = client.models.request["contents"][0]
        self.assertEqual(media_part.inline_data.data, b"media-bytes")


class OpenVttMediaTests(unittest.TestCase):
    @unittest.skipUnless(open_vtt.HAS_PYAV, "PyAV is not installed")
    def test_pyav_probes_and_decodes_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "sample.wav"
            with wave.open(str(media), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\x00\x00" * 1600)

            metadata = open_vtt.pyav_check(media)
            audio = open_vtt.load_audio_with_pyav(media)

        self.assertTrue(metadata["has_audio"])
        self.assertFalse(metadata["has_subtitles"])
        self.assertAlmostEqual(metadata["duration"], 0.1, places=2)
        self.assertEqual(len(audio), 1600)

    def test_ffprobe_failure_is_not_masked_by_pyav(self):
        with mock.patch.object(
            open_vtt, "run_command", return_value=(1, "", "invalid media")
        ), mock.patch.object(open_vtt, "pyav_check") as pyav_check:
            result = open_vtt.ffprobe_check(Path("bad.mp4"))

        self.assertEqual(result, {})
        pyav_check.assert_not_called()

    def test_ffprobe_missing_uses_pyav_fallback(self):
        expected = {"has_audio": True}
        with mock.patch.object(
            open_vtt, "run_command", return_value=(-1, "", "not found")
        ), mock.patch.object(open_vtt, "pyav_check", return_value=expected) as pyav_check:
            result = open_vtt.ffprobe_check(Path("sample.mp4"))

        self.assertEqual(result, expected)
        pyav_check.assert_called_once_with(Path("sample.mp4"))


if __name__ == "__main__":
    unittest.main()
