from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("", views.ModificationListView.as_view(), name="liste"),
]
