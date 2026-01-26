from google import genai
import base64
from decouple import config

gemini_client = genai.Client(
    api_key=config("GEMINI_KEY")
)

def generate_image_with_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash-image",
    needs_image: bool = False,
    reference_image: str = ""
) -> str:
    """
    Returns a base64-encoded PNG image string (NOT saved to disk).

    If needs_image=True and reference_image is provided, this performs
    an image-to-image refinement by sending the previous image + prompt.
    """

    print("Gemini Tool: generating image...")

    contents = []

    # If we need to refine, attach the reference image as inline_data
    print(f"Needs image: {needs_image}, reference image provided: {reference_image != ''}")
    if needs_image and reference_image:
        contents.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": reference_image,
            }
        })

        # Important: prompt should clearly describe *changes*, not restate everything
        # (but you can still do either).
        contents.append(prompt)
    else:
        # Prompt-only generation (your previous behavior)
        contents = [prompt]

    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
    )

    # Gemini responses can include multiple parts; return the first image part found
    for part in response.parts:
        if getattr(part, "inline_data", None) is not None:
            out_bytes = part.inline_data.data
            out_b64 = base64.b64encode(out_bytes).decode("utf-8")
            print("Done")
            return out_b64

    raise RuntimeError("Gemini did not return an image")
