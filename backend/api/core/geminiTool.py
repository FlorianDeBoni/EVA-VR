from google import genai
import base64
from decouple import config

gemini_client = genai.Client(
    api_key=config("GEMINI_KEY")
)

def generate_image_with_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash-image",
) -> str:
    """
    Returns a base64-encoded PNG image string (NOT saved to disk).
    """
    print("Gemini Tool: generating image...")

    response = gemini_client.models.generate_content(
        model=model,
        contents=[prompt],
    )

    for part in response.parts:
        if part.inline_data is not None:
            # raw bytes from Gemini
            image_bytes = part.inline_data.data

            # convert to base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")

            print("Done")
            # return *only* the base64 payload
            return b64

    raise RuntimeError("Gemini did not return an image")
