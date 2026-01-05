from django.urls import path
from .views import check_status

urlpatterns = [
    path("check", check_status, name="check")
]
