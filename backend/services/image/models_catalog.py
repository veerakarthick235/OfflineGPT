"""
Predefined catalogue of image generation models available for download.
"""
from dataclasses import dataclass, field
from typing import List

@dataclass
class ModelEntry:
    id:           str          # internal unique ID
    hf_repo:      str          # HuggingFace repo ID
    name:         str          # Display name
    description:  str
    size_gb:      float
    steps_default: int
    pipeline_type: str         # "StableDiffusionPipeline" | "StableDiffusionXLPipeline" | "AutoPipelineForText2Image"
    dtype:        str = "float32"  # "float16" on GPU, "float32" on CPU
    variant:      str = ""         # e.g. "fp16"
    tags:         List[str] = field(default_factory=list)

    @property
    def size_label(self) -> str:
        return f"{self.size_gb:.1f} GB"


CATALOG: List[ModelEntry] = [
    ModelEntry(
        id            = "sdxl-turbo",
        hf_repo       = "stabilityai/sdxl-turbo",
        name          = "SDXL Turbo",
        description   = "Ultra-fast generation in 1–4 steps. Best quality/speed ratio.",
        size_gb       = 6.7,
        steps_default = 4,
        pipeline_type = "AutoPipelineForText2Image",
        tags          = ["fast", "high-quality", "gpu-recommended"],
    ),
    ModelEntry(
        id            = "sd-1.5",
        hf_repo       = "runwayml/stable-diffusion-v1-5",
        name          = "Stable Diffusion 1.5",
        description   = "Classic SD model. Works well on CPU. Wide community support.",
        size_gb       = 4.0,
        steps_default = 20,
        pipeline_type = "StableDiffusionPipeline",
        tags          = ["classic", "cpu-friendly"],
    ),
    ModelEntry(
        id            = "dreamshaper-8",
        hf_repo       = "Lykon/dreamshaper-8",
        name          = "DreamShaper 8",
        description   = "Excellent photorealistic and artistic outputs. Very popular.",
        size_gb       = 2.0,
        steps_default = 20,
        pipeline_type = "StableDiffusionPipeline",
        tags          = ["photorealistic", "artistic", "popular"],
    ),
    ModelEntry(
        id            = "anything-v5",
        hf_repo       = "stablediffusionapi/anything-v5",
        name          = "Anything V5",
        description   = "Anime and illustration style. Vibrant, detailed artwork.",
        size_gb       = 2.1,
        steps_default = 20,
        pipeline_type = "StableDiffusionPipeline",
        tags          = ["anime", "illustration"],
    ),
]

CATALOG_MAP = {m.id: m for m in CATALOG}


def get_model(model_id: str) -> ModelEntry | None:
    return CATALOG_MAP.get(model_id)
