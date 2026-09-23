from django.urls import path

from . import views

app_name = "suivis"

urlpatterns = [
    path("", views.SuiviListView.as_view(), name="liste"),
    path("nouveau/", views.SuiviCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.SuiviUpdateView.as_view(), name="modifier"),
]
