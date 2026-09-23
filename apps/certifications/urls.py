from django.urls import path

from . import views

app_name = "certifications"

urlpatterns = [
    path("", views.CertificationListView.as_view(), name="liste"),
    path("nouveau/", views.CertificationCreateView.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.CertificationUpdateView.as_view(), name="modifier"),
]
