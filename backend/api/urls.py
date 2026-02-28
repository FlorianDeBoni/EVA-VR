from django.urls import path
from .views import chat, getCsrfToken, getPrompts, add_log

urlpatterns = [
    path("chat", chat, name="check"),
    path("csrf", getCsrfToken, name="csrf"),
    path("getPrompt", getPrompts, name="getPrompt"),
    path("addLog", add_log, name="add_log"),
]
