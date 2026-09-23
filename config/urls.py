from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="dashboard:public"), name="home"),
    path("dashboard/", include("apps.dashboard.urls")),
    path("beneficiaires/", include("apps.beneficiaires.urls")),
    path("formations/", include("apps.formations.urls")),
    path("certifications/", include("apps.certifications.urls")),
    path("insertions/", include("apps.insertions.urls")),
    path("suivis/", include("apps.suivis.urls")),
    path("satisfactions/", include("apps.satisfactions.urls")),
    path("rapports/", include("apps.reporting.urls")),
    path("soumissions/", include("apps.imports.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
