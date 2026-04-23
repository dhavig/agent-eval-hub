"""On-device model surface (skeleton).

Status: skeleton. Wraps a local Ollama endpoint but labels itself as
`provider="device"` so cross-surface runs produce the right QA signal
("cloud vs. device"). In production, swap the Ollama backend for a real
on-device quantized model (e.g. llama.cpp, MLX, Android AICore).

Use from CLI as `--provider device --model llama3.1`.
"""
from __future__ import annotations

import os

from agent_eval_hub.adapters.ollama import OllamaAdapter


class DeviceOllamaAdapter(OllamaAdapter):
    """Sibling of `OllamaAdapter` that self-identifies as an on-device surface.

    Semantic difference only — functionally it's Ollama. The rename matters for
    dashboards, divergence reports, and A/B comparisons where `provider="device"`
    communicates the right story."""

    provider = "device"

    def __init__(self, model: str = "llama3.1", base_url: str | None = None, timeout: float = 120.0):
        super().__init__(
            model=model,
            base_url=base_url or os.environ.get("DEVICE_OLLAMA_HOST", os.environ.get("OLLAMA_HOST")),
            timeout=timeout,
        )
