import json
from typing import List, Dict, Any
from .geminiTool import generate_image_with_gemini
from .wikimediaTool import fetch_wikimedia_image
from openai import AzureOpenAI
from decouple import config

# Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=config("AZURE_ENDPOINT"),
    api_key=config("AZURE_OPENAI_KEY"),
    api_version=config("AZURE_API_VERSION"),
    timeout=30,
)

GPT_COMPLETION_MODEL = config("GPT_COMPLETION_MODEL")

GEMINI_TOOLS = {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image using Gemini",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "output_path": {"type": "string"},
                },
                "required": ["prompt"],
            },
        },
    }

WIKIMEDIA_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_wikimedia_image",
        "description": (
            "Fetch a real, publicly licensed reference image from Wikimedia Commons. "
            "Only returns browser-renderable raster images (PNG, JPG, WEBP). Never PDFs, SVGs, or documents."
            "Use this tool before suggesting AI-generated images."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the image should visually represent"
                }
            },
            "required": ["query"]
        }
    }
}


# -----------------------------
# Maybe generate image
# -----------------------------
def maybe_generate_image(history: List[Dict[str, Any]]):
    response = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=history,
        tools=[GEMINI_TOOLS, WIKIMEDIA_IMAGE_TOOL],
        tool_choice="auto",
        temperature=1.0,
    )

    message = response.choices[0].message
    history.append(message)

    generated_images = []
    reference_images = []

    if message.tool_calls:
        for idx, tool_call in enumerate(message.tool_calls, start=1):
            args = json.loads(tool_call.function.arguments)

            # ---- Wikimedia tool ----
            if tool_call.function.name == "fetch_wikimedia_image":
                result = fetch_wikimedia_image(query=args["query"])

                if result:
                    ref_id = f"WIKI_{idx}"
                    reference_images.append({
                        "id": ref_id,
                        **result
                    })

                    history.append({
                        "role": "tool",
                        "name": tool_call.function.name,
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "id": ref_id,
                            "status": "found",
                            "image": result
                        })
                    })
                else:
                    history.append({
                        "role": "tool",
                        "name": tool_call.function.name,
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "status": "not_found"
                        })
                    })

            # ---- Gemini image generation ----
            elif tool_call.function.name == "generate_image":
                image_b64 = generate_image_with_gemini(prompt=args["prompt"])
                image_id = f"IMAGE_{idx}"

                generated_images.append({
                    "id": image_id,
                    "b64": image_b64
                })

                history.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "tool_call_id": tool_call.id,
                    "content": f"Image generated and stored as {image_id}"
                })

    return history, reference_images, generated_images

# -----------------------------
# Streaming text
# -----------------------------
def send_chat_completion_stream(history: List[Dict[str, Any]], model=GPT_COMPLETION_MODEL):
    response = client.chat.completions.create(
        model=model,
        messages=history,
        temperature=1.0,
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content