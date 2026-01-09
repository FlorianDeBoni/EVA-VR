import json
from typing import List, Dict, Any
from .geminiTool import generate_image_with_gemini
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

GEMINI_TOOLS = [
    {
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
]

# -----------------------------
# Maybe generate image
# -----------------------------
def maybe_generate_image(history: List[Dict[str, Any]]):
    """
    Sends history to Azure OpenAI.
    Generates images using Gemini if requested.
    Returns updated history + list of generated images.
    """
    response = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=history,
        tools=GEMINI_TOOLS,
        tool_choice="auto",
        temperature=1.0,
    )

    message = response.choices[0].message
    history.append(message)  # append assistant text

    generated_images = []

    if message.tool_calls:
        for idx, tool_call in enumerate(message.tool_calls, start=1):
            if tool_call.function.name == "generate_image":
                args = json.loads(tool_call.function.arguments)
                image_b64 = generate_image_with_gemini(prompt=args["prompt"])
                image_id = f"IMAGE_{idx}"

                generated_images.append({
                    "id": image_id,
                    "b64": image_b64
                })

                # Append tool message so Azure knows tool call is fulfilled
                history.append({
                    "role": "tool",
                    "name": tool_call.function.name,
                    "tool_call_id": tool_call.id,
                    "content": f"Image generated and stored as {image_id}"
                })

    return history, generated_images


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

    yield "[DONE]"
