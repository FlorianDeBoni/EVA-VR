# gemini_tools.py
from google import genai
from typing import Optional
from PIL import Image  # Make sure you have Pillow installed
import os
from decouple import config

# -----------------------------
# Gemini client
# -----------------------------
gemini_client = genai.Client(
    api_key=config("GEMINI_KEY")
)

import os

# -----------------------------
# Tool: image generation
# -----------------------------
def generate_image_with_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash-image",
    output_path: str = "generated_image.png",
) -> Optional[str]:
    """
    Generates an image using Gemini and saves it to disk.
    Returns the file path if successful.
    """

    print('Gemini Tool: generating image...')

    # ✅ Ensure output_path is a file, not a directory
    if os.path.isdir(output_path):
        # If output_path is a directory, append default filename
        output_path = os.path.join(output_path, "generated_image.png")

    # ✅ Ensure parent directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    response = gemini_client.models.generate_content(
        model=model,
        contents=[prompt],
    )

    for part in response.parts:
        if part.inline_data is not None:
            image = part.as_image()
            image.save(output_path)  # Now safe
            print(f"Image saved to {output_path}")
            return output_path

    print("No image generated.")
    return None