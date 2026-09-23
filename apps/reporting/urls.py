from django.urls import path

from . import views

app_name = "reporting"

urlpatterns = [
    path("", views.RapportsIndexView.as_view(), name="index"),
    path("cycle/<int:pk>/excel/", views.RapportCycleExcelView.as_view(), name="cycle_excel"),
]
