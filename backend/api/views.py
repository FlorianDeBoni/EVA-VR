from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from .core.azureLangchainAgent import maybe_generate_image, send_chat_completion_stream

@require_GET
def check_status(request):
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Using the tool generate a picture of a cat"},
    ]
    
    print("Start view")

    def event_stream():
        # Step 1: generate image (blocking)
        updated_history = maybe_generate_image(history)

        # Step 2: stream assistant's response
        for chunk in send_chat_completion_stream(updated_history):
            yield f"data: {chunk}\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
