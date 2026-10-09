import os
import unittest
from unittest.mock import Mock, patch

from app.services.ai_tryon import (
    TryOnError,
    _data_uri,
    generate_virtual_tryon,
    get_virtual_tryon_status,
)


class TryOnAdapterTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_TRYON_BACKEND": "provider",
            "AI_API_KEY": "test-key",
            "AI_API_URL": "https://api.fashn.ai",
            "AI_MODEL": "tryon-max",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_rejects_unsupported_mime(self):
        with self.assertRaises(TryOnError):
            _data_uri(b"image bytes", "image/gif")

    def test_rejects_empty_or_oversized_input(self):
        with self.assertRaises(TryOnError):
            _data_uri(b"", "image/jpeg")
        with self.assertRaises(TryOnError):
            _data_uri(b"x" * (8 * 1024 * 1024 + 1), "image/jpeg")

    def test_missing_provider_key_fails_without_fake_success(self):
        os.environ.pop("AI_API_KEY", None)
        with self.assertRaisesRegex(TryOnError, "No image was generated"):
            generate_virtual_tryon((b"person", "image/jpeg"), "https://example.com/garment.jpg")

    @patch("app.services.ai_tryon.requests.post")
    def test_real_provider_job_returns_job_id(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {"id": "job-123"}
        post.return_value = response
        result = generate_virtual_tryon(
            (b"person-image", "image/jpeg"),
            "https://example.com/garment.jpg",
        )
        self.assertEqual(result, {"mode": "live", "status": "processing", "job_id": "job-123"})
        self.assertIn("data:image/jpeg;base64,", post.call_args.kwargs["json"]["inputs"]["model_image"])
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 45))

    @patch("app.services.ai_tryon.requests.get")
    def test_completed_status_returns_real_output(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "status": "completed",
            "output": ["https://cdn.example.com/generated.jpg"],
        }
        get.return_value = response
        result = get_virtual_tryon_status("job-123")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output"], "https://cdn.example.com/generated.jpg")

    @patch("app.services.ai_tryon.requests.post")
    def test_provider_error_body_is_not_exposed(self, post):
        response = Mock(status_code=500)
        response.text = "sensitive provider diagnostic"
        post.return_value = response
        with self.assertRaisesRegex(TryOnError, "HTTP 500") as raised:
            generate_virtual_tryon((b"person", "image/jpeg"), "https://example.com/garment.jpg")
        self.assertNotIn("sensitive provider diagnostic", str(raised.exception))

    def test_local_backend_fails_closed_until_model_is_installed(self):
        os.environ["AI_TRYON_BACKEND"] = "local"
        with self.assertRaisesRegex(TryOnError, "not installed"):
            generate_virtual_tryon((b"person", "image/jpeg"), "https://example.com/garment.jpg")


if __name__ == "__main__":
    unittest.main()
