from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import CertificationForm
from .models import Certification


class CertificationListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Certification
    template_name = "certifications/liste.html"
    context_object_name = "certifications"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nb_types"] = self.get_queryset().values("type_certificat").distinct().count()
        return context


class CertificationCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Certification
    form_class = CertificationForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("certifications:liste")

    def form_valid(self, form):
        messages.success(self.request, "Certification enregistrée.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouvelle certification"
        context["retour_url"] = self.success_url
        return context


class CertificationUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Certification
    form_class = CertificationForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("certifications:liste")
    institution_lookup = "beneficiaire__institution"

    def form_valid(self, form):
        messages.success(self.request, "Certification mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        return context
