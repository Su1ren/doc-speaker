"""
cosyvoice_adapter.py – Lightweight wrapper for a locally hosted CosyVoice API.

The actual CosyVoice runtime must be set up separately. Point
``COSYVOICE_BASE_URL`` to the running service (e.g. http://localhost:8000),
and this helper will POST SSML text to ``/tts`` and write the returned audio
bytes to disk.
"""

import os
from typing import Optional

import requests


class CosyVoiceError(RuntimeError):
    """Raised when the CosyVoice HTTP API cannot fulfil a request."""


def cosyvoice_tts(
    ssml_text: str,
    output_path: str,
    speaker: str = "cosyvoice",
    base_url: Optional[str] = None,
    timeout: int = 60,
) -> str:
    """Send *ssml_text* to a CosyVoice HTTP endpoint and save the returned audio.

    The CosyVoice server is expected to expose ``POST /tts`` with JSON payload
    ``{"text": "...", "speaker": "...", "format": "mp3"}`` and to return raw
    audio bytes. Adjust the endpoint by setting ``COSYVOICE_BASE_URL`` or the
    *base_url* argument.
    """
    server = (base_url or os.getenv("COSYVOICE_BASE_URL") or "").rstrip("/")
    if not server:
        raise CosyVoiceError("COSYVOICE_BASE_URL is not configured.")

    url = f"{server}/tts"
    try:
        response = requests.post(
            url,
            json={"text": ssml_text, "speaker": speaker, "format": "mp3"},
            timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - network failure
        raise CosyVoiceError(f"Failed to reach CosyVoice at {url}: {exc}") from exc

    if response.status_code >= 400:
        raise CosyVoiceError(f"CosyVoice returned HTTP {response.status_code}: {response.text}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as fh:
        fh.write(response.content)
    return output_path
