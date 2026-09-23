from django.urls import path

from . import views

app_name = "beneficiaires"

urlpatterns = [
    path("", views.BeneficiaireListView.as_view(), name="liste"),
    path("nouveau/", views.BeneficiaireCreateView.as_view(), name="creer"),
    path("<str:pk>/modifier/", views.BeneficiaireUpdateView.as_view(), name="modifier"),
]
