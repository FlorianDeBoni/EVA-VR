from django.urls import path
from .views import chat, getCsrfToken, getPrompts

urlpatterns = [
    path("chat", chat, name="check"),
    path("csrf", getCsrfToken, name="csrf"),
    path("getPrompt", getPrompts, name="getPrompt"),
]
