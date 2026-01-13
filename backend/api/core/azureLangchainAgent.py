import json
from typing import List, Dict, Any

from openai import AzureOpenAI
from decouple import config

from .geminiTool import generate_image_with_gemini
from .wikimediaTool import fetch_reference_images

# -------------------------------------------------------------------
# Azure OpenAI client
# -------------------------------------------------------------------

client = AzureOpenAI(
    azure_endpoint=config("AZURE_ENDPOINT"),
    api_key=config("AZURE_OPENAI_KEY"),
    api_version=config("AZURE_API_VERSION"),
    timeout=30,
)

GPT_COMPLETION_MODEL = config("GPT_COMPLETION_MODEL")

# -------------------------------------------------------------------
# Tool definitions (CRITICAL: contracts must be accurate)
# -------------------------------------------------------------------

GEMINI_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "Generate an AI image using Gemini. "
            "This should ONLY be used if no suitable real-world reference image exists. "
            "Do NOT include image URLs or markdown. "
            "Image output will be handled by the system."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "A concrete, visual description of the image to generate"
                }
            },
            "required": ["prompt"],
        },
    },
}

REFERENCE_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_reference_images",
        "description": (
            "Fetch multiple candidate reference images for a real-world concept. "
            "Returns a LIST of plausible images from Wikipedia or Wikimedia Commons. "
            "You MUST choose exactly ONE image that best represents the concept visually, "
            "or explicitly reject all candidates if none are suitable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A concise, concrete, real-world description suitable for image search. "
                        "Avoid abstract language."
                    )
                }
            },
            "required": ["query"]
        }
    }
}

# -------------------------------------------------------------------
# Tool-aware image handling
# -------------------------------------------------------------------

def maybe_generate_image(history: List[Dict[str, Any]]):
    """
    Azure-safe tool handling with strict image selection.

    Flow:
    1. Assistant decides which tools to call
    2. Tools return candidates / generated images
    3. Assistant performs STRICT image selection (machine-only)
    4. Normal narration happens later during streaming
    """

    # ------------------------------------------------------------------
    # 1️⃣ Initial assistant call (may contain tool calls)
    # ------------------------------------------------------------------
    response = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=history,
        tools=[REFERENCE_IMAGE_TOOL, GEMINI_IMAGE_TOOL],
        tool_choice="auto",
        temperature=0,
    )

    assistant_message = response.choices[0].message
    history.append(assistant_message)

    chosen_reference_images: List[Dict[str, Any]] = []
    generated_images: List[Dict[str, Any]] = []

    # No tools → nothing to do
    if not assistant_message.tool_calls:
        return history, chosen_reference_images, generated_images

    # ------------------------------------------------------------------
    # 2️⃣ Respond to ALL tool calls (Azure requirement)
    # ------------------------------------------------------------------
    reference_candidates_by_call: Dict[str, List[Dict[str, Any]]] = {}

    for tool_call in assistant_message.tool_calls:
        args = json.loads(tool_call.function.arguments)

        # ---- Reference image retrieval
        if tool_call.function.name == "fetch_reference_images":
            candidates = fetch_reference_images(query=args["query"])
            reference_candidates_by_call[tool_call.id] = candidates

            if not candidates:
                history.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "instruction": "No reference images were found.",
                        "response_format": "Respond with NO_SUITABLE_IMAGE."
                    })
                })
            else:
                history.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "instruction": (
                            "IMAGE SELECTION TASK.\n"
                            "Choose EXACTLY ONE image ID from the list below.\n"
                            "If none are suitable, respond with NO_SUITABLE_IMAGE."
                        ),
                        "response_format": (
                            "Respond with ONLY one of:\n"
                            "CHOSEN_IMAGE_ID: <id>\n"
                            "NO_SUITABLE_IMAGE"
                        ),
                        "candidates": candidates
                    })
                })

        # ---- AI image generation
        elif tool_call.function.name == "generate_image":
            image_b64 = generate_image_with_gemini(prompt=args["prompt"])
            image_id = f"IMAGE_{len(generated_images) + 1}"

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

    # ------------------------------------------------------------------
    # 3️⃣ STRICT image-selection call (NO narration allowed)
    # ------------------------------------------------------------------
    selection_prompt = history + [{
        "role": "system",
        "content": (
            "IMAGE SELECTION MODE.\n\n"
            "Respond with ONLY one of the following:\n"
            "- CHOSEN_IMAGE_ID: <id>\n"
            "- NO_SUITABLE_IMAGE\n\n"
            "Do NOT include explanations or descriptions."
        )
    }]

    selection = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=selection_prompt,
        temperature=0,
    )

    selection_message = selection.choices[0].message
    history.append(selection_message)

    content = (selection_message.content or "").strip()

    # ------------------------------------------------------------------
    # 4️⃣ Parse selection
    # ------------------------------------------------------------------
    if content.startswith("CHOSEN_IMAGE_ID:"):
        chosen_id = content.replace("CHOSEN_IMAGE_ID:", "").strip()

        for candidates in reference_candidates_by_call.values():
            for img in candidates:
                if img.get("id") == chosen_id:
                    chosen_reference_images.append(img)
                    break
            if chosen_reference_images:
                break

    elif content.upper() == "NO_SUITABLE_IMAGE":
        # Prevent phantom image narration
        history.append({
            "role": "system",
            "content": (
                "No reference image was selected. "
                "Do NOT refer to any image in your response."
            )
        })

    return history, chosen_reference_images, generated_images


# -------------------------------------------------------------------
# Streaming assistant text (tool-safe)
# -------------------------------------------------------------------

def send_chat_completion_stream(
    history: List[Dict[str, Any]],
    model: str = GPT_COMPLETION_MODEL
):
    response = client.chat.completions.create(
        model=model,
        messages=history,
        temperature=0,
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
