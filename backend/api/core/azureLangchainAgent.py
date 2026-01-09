# views.py
from .geminiTool import generate_image_with_gemini
from typing import Generator, List, Dict, Any
import json
from openai import AzureOpenAI
import os
from decouple import config

# Azure OpenAI client setup...
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
# maybe_generate_image function
# -----------------------------
def maybe_generate_image(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Runs a non-streamed call to see if an image should be generated.
    Executes the Gemini tool if requested.
    Returns updated history.
    """
    response = client.chat.completions.create(
        model=GPT_COMPLETION_MODEL,
        messages=history,
        tools=GEMINI_TOOLS,
        tool_choice="auto",
        temperature=1.0,
    )

    message = response.choices[0].message

    # No tool call → just continue
    if not message.tool_calls:
        history.append(message)
        return history

    history.append(message)

    for tool_call in message.tool_calls:
        if tool_call.function.name == "generate_image":
            args = json.loads(tool_call.function.arguments)
            image_path = generate_image_with_gemini(
                prompt=args["prompt"],
                output_path=args.get("output_path", "generated_image.png"),
            )

            history.append({
                "role": "tool",
                "name": tool_call.function.name,
                "tool_call_id": tool_call.id,
                "content": f"Image generated at {image_path}",
            })

    return history

def send_chat_completion_stream(
    history: List[Dict],
    model: str = GPT_COMPLETION_MODEL,
) -> Generator[str, None, None]:
    """
    Streams chat completion from Azure OpenAI.
    Assumes image has already been generated.
    """
    # Stream final response from the model
    response = client.chat.completions.create(
        model=model,
        messages=history,
        temperature=1.0,
        stream=True,  # streaming enabled
    )

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

    yield "[DONE]"