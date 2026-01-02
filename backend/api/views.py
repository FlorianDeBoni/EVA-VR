from django.http import JsonResponse

# Create your views here.
def check_status(request):
    return JsonResponse({"content": "ok"}, status=200)