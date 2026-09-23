from django.urls import path

from . import views

app_name = "insertions"

urlpatterns = [
    path("", views.InsertionListView.as_view(), name="liste"),
    path("nouveau/", views.InsertionCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.InsertionUpdateView.as_view(), name="modifier"),
]
