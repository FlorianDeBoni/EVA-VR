import json
from typing import List, Dict, Any

from openai import AzureOpenAI
from decouple import config
import time

from .geminiTool import generate_image_with_gemini
from .serpapiTool import fetch_reference_images

from .toolDefinitions import GEMINI_IMAGE_TOOL, REFERENCE_IMAGE_TOOL

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
# Tool-aware image handling
# -------------------------------------------------------------------

def maybe_generate_image(history: List[Dict[str, Any]], reference_image: str = ""):
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
                            "Choose up to THREE distinct image IDs from the list below.\n"
                            "If none are suitable, respond with NO_SUITABLE_IMAGE."
                        ),
                        "response_format": (
                            "Respond with ONLY one of:\n"
                            "CHOSEN_IMAGE_IDS: <id>, <id>, <id>\n"
                            "NO_SUITABLE_IMAGE"
                        ),
                        "candidates": candidates
                    })
                })

        # ---- AI image generation
        elif tool_call.function.name == "generate_image":
            image_b64 = generate_image_with_gemini(prompt=args["prompt"], needs_image=args.get("needs_image", False), reference_image=reference_image)
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
            "Select 2 to 4 visually distinct reference images across all candidate lists.\n"
            "Respond with ONLY one of the following:\n"
            "- CHOSEN_IMAGE_IDS: <id>, <id>, ...\n"
            "- NO_SUITABLE_IMAGE\n\n"
            "Do NOT include explanations or descriptions."
        )
    }]

    selection = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=selection_prompt,
    )

    selection_message = selection.choices[0].message
    history.append(selection_message)

    content = (selection_message.content or "").strip()

    # ------------------------------------------------------------------
    # 4️⃣ Parse selection
    # ------------------------------------------------------------------
    if content.startswith("CHOSEN_IMAGE_IDS:"):
        chosen_ids = [
            image_id.strip()
            for image_id in content.replace("CHOSEN_IMAGE_IDS:", "", 1).split(",")
            if image_id.strip()
        ][:4]

        candidates_by_id = {
            img.get("id"): img
            for candidates in reference_candidates_by_call.values()
            for img in candidates
            if img.get("id")
        }

        for chosen_id in chosen_ids:
            image = candidates_by_id.get(chosen_id)
            if image and image not in chosen_reference_images:
                chosen_reference_images.append(image)

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
        stream=True,
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            for c in chunk.choices[0].delta.content:
                yield c
                time.sleep(0.01)  # slight delay for smoother streaming
