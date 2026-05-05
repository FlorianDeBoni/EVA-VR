from django.urls import path
from .views import chat, getCsrfToken, getPrompts, add_log, add_feedback, update_prompt

urlpatterns = [
    path("chat", chat, name="check"),
    path("csrf", getCsrfToken, name="csrf"),
    path("getPrompt", getPrompts, name="getPrompt"),
    path("addLog", add_log, name="add_log"),
    path("addFeedback", add_feedback, name="add_feedback"),
    path("updatePrompt", update_prompt, name="updatePrompt"),
]
