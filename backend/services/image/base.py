"""
Abstract base for all image generation providers.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, AsyncIterator


@dataclass
class ImageResult:
    filename:  str
    path:      str
    url:       str          # e.g.  /api/images/file/<filename>
    prompt:    str
    width:     int
    height:    int
    steps:     int
    seed:      int
    provider:  str          # "diffusers" | "a1111" | "comfyui"
    model_id:  str
    error:     Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class ImageProvider(ABC):
    """
    All providers implement this interface.
    Providers are stateless wrappers; the ImageManager owns lifecycle.
    """

    name: str = "base"

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this provider can generate images right now."""

    @abstractmethod
    async def generate(
        self,
        prompt:          str,
        negative_prompt: str  = "",
        width:           int  = 512,
        height:          int  = 512,
        steps:           int  = 20,
        cfg_scale:       float = 7.0,
        seed:            int  = -1,
        model_id:        str  = "",
        output_path:     Path = Path("."),
    ) -> ImageResult:
        """Generate an image and return its result metadata."""

    @property
    def provider_name(self) -> str:
        return self.name
