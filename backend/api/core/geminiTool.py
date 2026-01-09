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

# -----------------------------
# Tool: image generation
# -----------------------------
def generate_image_with_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash-image",
    output_path: str = "generated_image.png",
) -> str:
    print("Gemini Tool: generating image...")

    # --- Normalize the output path ---
    # Case 1: output_path is "." or "" -> save in CWD with default file name
    if not output_path or output_path in (".", "./"):
        output_path = "generated_image.png"

    # Case 2: output_path is a directory -> append a filename
    if os.path.isdir(output_path):
        output_path = os.path.join(output_path, "generated_image.png")

    # Ensure folder exists
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    # --- Generate image ---
    response = gemini_client.models.generate_content(
        model=model,
        contents=[prompt],
    )

    for part in response.parts:
        if part.inline_data is not None:
            image = part.as_image()
            image.save(output_path)
            print(f"Image saved to {output_path}")
            return output_path

    raise RuntimeError("Gemini did not return an image")