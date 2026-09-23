from django.urls import path

from . import views

app_name = "formations"

urlpatterns = [
    path("", views.FormationListView.as_view(), name="liste"),
    path("nouveau/", views.FormationCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.FormationUpdateView.as_view(), name="modifier"),
]
