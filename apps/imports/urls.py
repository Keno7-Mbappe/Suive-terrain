from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("", views.SoumissionListView.as_view(), name="liste"),
    path("actualiser/", views.SoumissionActualiserView.as_view(), name="actualiser"),
    path("<int:pk>/", views.SoumissionDetailView.as_view(), name="detail"),
    path("<int:pk>/corriger/", views.SoumissionCorrigerView.as_view(), name="corriger"),
    path("<int:pk>/valider/", views.SoumissionValiderView.as_view(), name="valider"),
    path("<int:pk>/reessayer/", views.SoumissionReessayerView.as_view(), name="reessayer"),
    path("<int:pk>/supprimer/", views.SoumissionSupprimerView.as_view(), name="supprimer"),
    path("<int:pk>/doublon/", views.SoumissionMarquerDoublonView.as_view(), name="marquer_doublon"),
]
