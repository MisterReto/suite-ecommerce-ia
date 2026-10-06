"""Abstraction over the accepted pipeline, not an alternative implementation."""

from typing import Protocol
import creative_pipeline


class ImageProvider(Protocol):
    name: str
    model: str

    def generate(self, *args, **kwargs): ...


class GeminiProvider:
    name = "gemini"
    model = creative_pipeline.IMAGE_MODEL

    def generate(self, *args, **kwargs):
        return creative_pipeline.generate(*args, **kwargs)


class UnconfiguredProvider:
    def generate(self, *args, **kwargs):
        raise RuntimeError(
            "Proveedor preparado pero no configurado; Gemini sigue siendo el proveedor activo."
        )


class FluxProvider(UnconfiguredProvider):
    name = "flux"


class OpenAIProvider(UnconfiguredProvider):
    name = "openai"


class PhotoRoomProvider(UnconfiguredProvider):
    name = "photoroom"


class ImageGenerationService:
    """Reuses brief, generation, logo, QA and corrections exactly as accepted."""

    provider = GeminiProvider()

    def plan(self, value, current, progress):
        from studio_api import creative_plan

        return creative_plan(value, current, progress)

    def generate(self, value, current, slot, prompt, styles, **options):
        from studio_api import make_image

        make_image(value, current, slot, prompt, styles, **options)
        return current["images"][slot]
