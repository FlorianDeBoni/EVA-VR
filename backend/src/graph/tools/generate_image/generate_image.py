import base64
import io
from functools import lru_cache

from openai import OpenAI

from backend.infra.AIClient import AIClient
from backend.src.graph.tools.generate_image.schemas import GeneratedImage, ImageGenerationError
from backend.src.settings.envManager import EnvKeyName, EnvManager
from backend.src.settings.LogManager import LogManager


class ImageGeneratorService:
    """Generates (or edits) images with OpenAI.

        generator = get_image_generator_service()
        image = generator.generate("a pavilion at dusk")

    Model and past-image limit come from .env.backend (OPENAI_IMAGE_MODEL,
    MAX_PAST_IMAGES) unless passed explicitly. The OpenAI client is created
    lazily and cached.
    """

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        max_past_images: int | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._max_past_images = max_past_images
        self.logger = LogManager.get_logger(__name__)

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = AIClient.from_env().get_client()
        return self._client

    @property
    def model(self) -> str:
        return self._model or EnvManager.get_env_variable(EnvKeyName.KEY_OPENAI_IMAGE_MODEL)

    @property
    def max_past_images(self) -> int:
        if self._max_past_images is not None:
            return self._max_past_images
        return int(EnvManager.get_env_variable(EnvKeyName.KEY_MAX_PAST_IMAGES))

    def generate(
        self,
        prompt: str,
        past_images: list[GeneratedImage] | tuple[GeneratedImage, ...] = (),
    ) -> GeneratedImage:
        """Generate an image from a prompt, optionally iterating on past images.

        With past images the prompt edits them (images.edit); without, it creates a new
        image (images.generate). Pass the previous result back to keep iterating.
        """
        if len(past_images) > self.max_past_images:
            raise ValueError(f"at most {self.max_past_images} past images, got {len(past_images)}")

        self.logger.info("Generating image (%d past images)", len(past_images))
        if past_images:
            files = []
            for i, img in enumerate(past_images):
                buffer = io.BytesIO(img.data)
                buffer.name = f"past_{i}.{img.mime_type.split('/')[-1]}"
                files.append(buffer)
            resp = self.client.images.edit(model=self.model, image=files, prompt=prompt)
        else:
            resp = self.client.images.generate(model=self.model, prompt=prompt)

        if not resp.data or not resp.data[0].b64_json:
            raise ImageGenerationError("OpenAI returned no image for this prompt")
        return GeneratedImage(base64.b64decode(resp.data[0].b64_json), "image/png")


@lru_cache(maxsize=1)
def get_image_generator_service() -> ImageGeneratorService:
    """Shared default service instance."""
    return ImageGeneratorService()
