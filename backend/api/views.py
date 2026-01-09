from django.http import StreamingHttpResponse
from .core.azureLangchainAgent import maybe_generate_image, send_chat_completion_stream
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def chat(request):
    # Parse JSON body
    try:
        body = json.loads(request.body.decode('utf-8'))
        message = body.get("message")
        history = body.get("history", [])
        
        print(f"Received message: {message}")
        print(f"Received history: {len(history)} messages")
        
    except json.JSONDecodeError:
        return StreamingHttpResponse(
            "data: " + json.dumps({"type": "error", "message": "Invalid JSON"}) + "\n\n",
            content_type="text/event-stream"
        )

    if not message:
        return StreamingHttpResponse(
            "data: " + json.dumps({"type": "error", "message": "No message provided"}) + "\n\n",
            content_type="text/event-stream"
        )

    # Build the full conversation history with system message
    full_history = [
        {"role": "system", "content": "You are a helpful assistant. You have access to a tool generating images. When you use it, **always** insert image placeholders like [IMAGE_1] instead of Markdown."}
    ]
    
    for msg in history:
        if msg.get("content"):
            full_history.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    print(full_history)

    def event_stream():
        # 1️⃣ Generate images and updated history
        updated_history, generated_images = maybe_generate_image(full_history)

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