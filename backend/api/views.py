from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET
from .core.AzureLangchainAgent import send_chat_completion_stream


@require_GET
def check_status(request):
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Generate a long text"},
    ]

    def event_stream():
        for chunk in send_chat_completion_stream(history):
            # SSE format
            yield f"data: {chunk}\n\n"

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
