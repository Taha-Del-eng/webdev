"""Safe adapter for real virtual try-on providers.

Local inference is intentionally not advertised as available until a compatible,
commercially permitted local model and weights are explicitly installed. No fake result
or silent paid-provider fallback is ever returned.
"""
import base64
import os
from urllib.parse import urlparse

import requests


class TryOnError(Exception):
    """A user-safe virtual try-on failure."""


ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT = (5, 45)
STATUS_TIMEOUT = (5, 20)
LOCAL_UNAVAILABLE = (
    "Local AI Try-On is not installed. This computer does not currently have a "
    "verified, commercially permitted local model and weights. No image was "
    "generated. Configure an approved provider or install a compatible model integration."
)


def _data_uri(raw: bytes, mime: str) -> str:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise TryOnError("Please upload a non-empty image smaller than 8 MB.")
    if mime not in ALLOWED_MIME_TYPES:
        raise TryOnError("Use a JPG, PNG, or WebP image.")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _provider_config():
    backend = os.getenv("AI_TRYON_BACKEND", "provider").strip().lower()
    if backend != "provider":
        raise TryOnError("AI Try-On backend configuration is invalid.")
    key = os.getenv("AI_API_KEY", "").strip()
    if not key:
        raise TryOnError("AI Try-On provider API key is not configured.")
    url = os.getenv("AI_API_URL", "https://api.fashn.ai").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise TryOnError("AI provider URL must be a valid HTTPS URL.")
    model = os.getenv("AI_MODEL", "tryon-max").strip()
    if not model or len(model) > 120:
        raise TryOnError("AI model configuration is invalid.")
    return key, url, model


def generate_virtual_tryon(user_image, clothing_image):
    """Submit a genuine provider job. Returns a job ID, never a fabricated image."""
    backend = os.getenv("AI_TRYON_BACKEND", "provider").strip().lower()
    if backend == "local":
        return {"mode": "unavailable", "status": "unavailable", "message": LOCAL_UNAVAILABLE}
    if backend != "provider":
        raise TryOnError("AI Try-On backend configuration is invalid.")
    if not os.getenv("AI_API_KEY", "").strip():
        return {
            "mode": "unavailable",
            "status": "unavailable",
            "message": "AI Try-On is not configured. Set AI_API_KEY for the external provider. No image was generated.",
        }

    key, url, model = _provider_config()
    if isinstance(user_image, tuple):
        raw, mime = user_image
        model_image = _data_uri(raw, mime)
    elif isinstance(user_image, str) and user_image.startswith("https://"):
        model_image = user_image
    else:
        raise TryOnError("The person image could not be processed.")

    if not isinstance(clothing_image, str) or not clothing_image.startswith("https://"):
        raise TryOnError("The selected product image is unavailable.")

    payload = {
        "model_name": model,
        "inputs": {
            "model_image": model_image,
            "product_image": clothing_image,
            "return_base64": False,
        },
    }
    try:
        response = requests.post(
            f"{url}/v1/run",
            json=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code >= 400:
            raise TryOnError(f"AI provider request failed (HTTP {response.status_code}).")
        data = response.json()
    except requests.Timeout as exc:
        raise TryOnError("AI generation timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise TryOnError("AI provider could not be reached. Please retry.") from exc
    except ValueError as exc:
        raise TryOnError("AI provider returned an unreadable response.") from exc

    job_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(job_id, str) or not job_id or len(job_id) > 255:
        raise TryOnError("AI provider did not return a valid generation job.")
    return {"mode": "live", "status": "processing", "job_id": job_id}


def get_virtual_tryon_status(job_id):
    """Fetch status for an existing provider job without leaking provider internals."""
    key, url, _model = _provider_config()
    if not isinstance(job_id, str) or not job_id or len(job_id) > 255:
        raise TryOnError("The try-on job is invalid.")
    try:
        response = requests.get(
            f"{url}/v1/status/{job_id}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=STATUS_TIMEOUT,
        )
        if response.status_code >= 400:
            raise TryOnError(f"AI status request failed (HTTP {response.status_code}).")
        data = response.json()
    except requests.Timeout as exc:
        raise TryOnError("Checking AI generation timed out. Please retry.") from exc
    except requests.RequestException as exc:
        raise TryOnError("AI provider could not be reached. Please retry.") from exc
    except ValueError as exc:
        raise TryOnError("AI provider returned an unreadable status.") from exc

    if not isinstance(data, dict):
        raise TryOnError("AI provider returned an invalid status.")
    status = data.get("status")
    if status not in {"queued", "processing", "completed", "failed", "starting"}:
        raise TryOnError("AI provider returned an unknown generation status.")
    output = data.get("output")
    if isinstance(output, list):
        output = output[0] if output else None
    if status == "completed" and not isinstance(output, str):
        raise TryOnError("AI generation completed without a result image.")
    return {
        "mode": "live",
        "status": status,
        "output": output if isinstance(output, str) else None,
        "error": "AI generation failed. Please try again." if status == "failed" else None,
    }
