from django.urls import path

from . import views

app_name = "satisfactions"

urlpatterns = [
    path("", views.SatisfactionListView.as_view(), name="liste"),
    path("nouveau/", views.SatisfactionCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.SatisfactionUpdateView.as_view(), name="modifier"),
    path("institutions/", views.SatisfactionInstitutionListView.as_view(), name="liste_institution"),
    path("institutions/nouveau/", views.SatisfactionInstitutionCreateView.as_view(), name="creer_institution"),
    path("institutions/<int:pk>/modifier/", views.SatisfactionInstitutionUpdateView.as_view(), name="modifier_institution"),
]
