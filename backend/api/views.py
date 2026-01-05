from django.http import JsonResponse
from .core.AzureLangchainAgent import send_chat_completion_stream

# Create your views here.
def check_status(request):
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Generate a long text"},
    ]

    for chunk in send_chat_completion_stream(history):
            print(chunk)
    return JsonResponse({"content": "ok"}, status=200)