import base64

from langchain_core.tools import tool

from backend.src.graph.tools.generate_image.generate_image import get_image_generator_service
from backend.src.graph.tools.generate_image.schemas import GenerateImageInput


@tool("generate_image", args_schema=GenerateImageInput)
def generate_image(prompt: str) -> str:
    """Generate an image from a text description.

    Returns the generated PNG image as a base64-encoded string.
    """
    image = get_image_generator_service().generate(prompt)
    return base64.b64encode(image.data).decode()
