"""
Image Generation Tool — generate images from text prompts.

Registered triggers: all image generation patterns from the original intent.py
(This replaces the hardcoded img_intent check in chat.py)
"""
from __future__ import annotations
from ..tool_registry import registry, ToolResult


@registry.tool(
    name        = "image_generate",
    description = "Generate, create, draw, or paint an image from a text description",
    fast_triggers = [
        r"(generate|create|make|draw|paint|render|produce|design|illustrate)\s+(an?\s+)?(image|picture|photo|illustration|artwork|painting|drawing|sketch|portrait|wallpaper|poster)\s+of\b",
        r"\b(image|picture|photo|illustration|artwork|painting|drawing|sketch)\s+of\s+",
        r"\bshow\s+me\s+(an?\s+)?(image|picture|photo|illustration|painting|drawing)\s+(of|showing)\b",
        r"\b(visualize|visualise)\s+",
        r"\bi\s+want\s+(an?\s+)?(image|picture|photo|illustration|painting)\s+(of|showing|that)\b",
        r"\b(generate|create|make|produce)\s+(an?\s+)?(AI\s+)?(art|image|picture|photo|illustration)\b",
        r"\bdraw\s+(me\s+)?(an?\s+)?",
        r"\bpaint\s+(me\s+)?(an?\s+)?",
        r"\b(portrait|landscape|wallpaper|poster|thumbnail)\s+of\b",
        r"\b(cute|realistic|fantasy|cyberpunk|anime)\s+(character|robot|cat|dog|person|scene)\b",
        r"\btext.?to.?image\b",
    ],
)
async def image_generate_tool(prompt: str = "", **kwargs) -> ToolResult:
    """
    Generate an image. The actual generation is handled by the executor
    via a special flag — this just validates and returns the intent.
    
    The executor checks for tool_name == "image_generate" and runs
    the full image generation SSE flow.
    """
    return ToolResult(
        tool    = "image_generate",
        success = True,
        data    = {"prompt": prompt},
        label   = f"Generating image: {prompt[:60]}...",
        metadata= {"requires_streaming": True, "prompt": prompt},
    )
