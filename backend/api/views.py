from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path
import json
import re

from .core.azureLangchainAgent import (
    maybe_generate_image,
    send_chat_completion_stream,
)

@csrf_exempt
def chat(request):
    # --------------------------------------------------
    # Parse JSON body
    # --------------------------------------------------
    try:
        body = json.loads(request.body.decode("utf-8"))
        message = body.get("message")
        history = body.get("history", [])
        reference_image = body.get("reference_image", "")
    except json.JSONDecodeError:
        return StreamingHttpResponse(
            "data: " + json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }) + "\n\n",
            content_type="text/event-stream"
        )

    if not message:
        return StreamingHttpResponse(
            "data: " + json.dumps({
                "type": "error",
                "message": "No message provided"
            }) + "\n\n",
            content_type="text/event-stream"
        )

    # --------------------------------------------------
    # Load system prompt
    # --------------------------------------------------
    current_dir = Path(__file__).parent
    prompt_path = current_dir / "core" / "prompts" / "gpt_prompt.md"

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # --------------------------------------------------
    # Build conversation history
    # IMPORTANT:
    # - NO placeholder instructions
    # - Images are handled as events, not text
    # --------------------------------------------------
    full_history = [
        {"role": "system", "content": system_prompt}
    ]

    for msg in history:
        if msg.get("content"):
            full_history.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # --------------------------------------------------
    # SSE event stream
    # --------------------------------------------------
    def event_stream():
        # 1️⃣ Let the agent handle tools + image decisions
        updated_history, reference_images, generated_images = (
            maybe_generate_image(full_history, reference_image=reference_image)
        )

        # 2️⃣ Send reference images chosen by the LLM (FIRST)
        for img in reference_images:
            payload = json.dumps({
                "type": "image",
                "id": img["id"],
                "url": img["url"],
                "source": img.get("source"),
                "title": img.get("title"),
            })
            print(f"Reference image: {img}")
            yield f"data: {payload}\n\n"

        # 3️⃣ Send AI-generated images (SECOND)
        for img in generated_images:
            payload = json.dumps({
                "type": "image",
                "id": img["id"],
                "b64": img["b64"],
            })
            print(f"Generated image")
            yield f"data: {payload}\n\n"

        def strip_image_urls(text: str) -> str:
            return re.sub(r'https?://\S+\.(jpg|jpeg|png|webp)\S*', '', text)

        for chunk in send_chat_completion_stream(updated_history):
            clean = strip_image_urls(chunk)
            payload = json.dumps({
                "type": "text",
                "delta": clean
            })
            yield f"data: {payload}\n\n"

        # 5️⃣ End of stream
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
