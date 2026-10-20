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


class FakeClient:
    def __init__(self):
        self.models = FakeModels()
        self.closed = False

    def close(self):
        self.closed = True


class OpenVttAdcTests(unittest.TestCase):
    def test_create_client_uses_vertex_adc_configuration(self):
        with mock.patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "GOOGLE_CLOUD_LOCATION": "test-location",
            },
        ), mock.patch.object(open_vtt.genai, "Client") as client_class:
            open_vtt.create_gemini_client()

        client_class.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="test-location",
        )

    def test_call_gemini_sends_local_media_inline(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.md"
            subtitles = root / "subtitles.vtt"
            media = root / "sample.m4a"
            prompt.write_text("Analyze at {{THINKING_LEVEL}} effort.", encoding="utf-8")
            subtitles.write_text("WEBVTT\n", encoding="utf-8")
            media.write_bytes(b"media-bytes")

            result = open_vtt.call_gemini(
                prompt,
                subtitles,
                media,
                client=client,
            )

        self.assertEqual(result["vtt"], "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nTest")
        self.assertEqual(client.models.request["model"], "gemini-2.5-flash")
        media_part, prompt_text = client.models.request["contents"]
        self.assertEqual(media_part.inline_data.mime_type, "audio/mp4")
        self.assertEqual(media_part.inline_data.data, b"media-bytes")
        self.assertIn("Analyze at HIGH effort.", prompt_text)
        self.assertFalse(client.closed)

    @unittest.skipUnless(open_vtt.HAS_PYAV, "PyAV is not installed")
    def test_pyav_probes_and_decodes_audio_without_ffprobe(self):
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


if __name__ == "__main__":
    unittest.main()
