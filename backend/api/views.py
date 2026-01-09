from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from .core.azureLangchainAgent import maybe_generate_image, send_chat_completion_stream
import json

@require_GET
def check_status(request):
    history = [
        {"role": "system", "content": "You are a helpful assistant. You have access to a tool generating images. When you use it, **always** insert image placeholders like [IMAGE_1] instead of Markdown."},
        {"role": "user", "content": "Tell a short story, no illustration."},
    ]

    def event_stream():
        # 1️⃣ Generate images and updated history
        updated_history, generated_images = maybe_generate_image(history)

        # 2️⃣ Send image events first
        for img in generated_images:
            payload = json.dumps({
                "type": "image",
                "id": img["id"],
                "b64": img["b64"]
            })
            yield f"data: {payload}\n\n"

        # 3️⃣ Stream text with placeholders [IMAGE_1], [IMAGE_2], etc.
        for chunk in send_chat_completion_stream(updated_history):
            payload = json.dumps({
                "type": "text",
                "delta": chunk
            })
            yield f"data: {payload}\n\n"

        # 4️⃣ End of stream
        yield "data: [DONE]\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
