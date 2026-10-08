import base64, os, requests

class TryOnError(Exception):
    pass

def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

def generate_virtual_tryon(user_image, clothing_image):
    """Submit a real FASHN try-on job; never exposes the API key to the browser."""
    key = os.getenv("AI_API_KEY")
    url = os.getenv("AI_API_URL", "https://api.fashn.ai").rstrip("/")
    model = os.getenv("AI_MODEL", "tryon-max")
    if not key:
        return {"mode": "unavailable", "status": "unavailable", "message": "AI Try-On is not configured. Add AI_API_KEY to enable live generation."}
    if isinstance(user_image, tuple):
        raw, mime = user_image
        model_image = _data_uri(raw, mime)
    else:
        model_image = user_image
    payload = {"model_name": model, "inputs": {"model_image": model_image, "product_image": clothing_image, "return_base64": False}}
    r = requests.post(f"{url}/v1/run", json=payload, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=30)
    if r.status_code >= 400:
        raise TryOnError(r.text[:500])
    data = r.json()
    if not data.get("id"):
        raise TryOnError(data.get("error") or "AI provider did not return a prediction id.")
    return {"mode": "live", "status": "processing", "job_id": data["id"]}

def get_virtual_tryon_status(job_id):
    key = os.getenv("AI_API_KEY")
    url = os.getenv("AI_API_URL", "https://api.fashn.ai").rstrip("/")
    if not key:
        return {"mode": "mock", "status": "mock"}
    r = requests.get(f"{url}/v1/status/{job_id}", headers={"Authorization": f"Bearer {key}"}, timeout=20)
    if r.status_code >= 400:
        raise TryOnError(r.text[:500])
    data = r.json()
    return {"mode": "live", "status": data.get("status"), "output": (data.get("output") or [None])[0], "error": data.get("error")}
