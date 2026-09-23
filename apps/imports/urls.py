from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("", views.SoumissionListView.as_view(), name="liste"),
    path("<int:pk>/reessayer/", views.SoumissionReessayerView.as_view(), name="reessayer"),
    path("<int:pk>/doublon/", views.SoumissionMarquerDoublonView.as_view(), name="marquer_doublon"),
]
