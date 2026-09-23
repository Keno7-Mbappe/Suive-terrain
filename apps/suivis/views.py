from django.contrib import messages
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import SuiviForm
from .models import Suivi


class SuiviListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Suivi
    template_name = "suivis/liste.html"
    context_object_name = "suivis"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        total = queryset.count()
        joints = queryset.filter(issue_contact="joint").count()
        context["nb_joints"] = joints
        context["taux_joignabilite"] = round(joints / total * 100, 1) if total else 0
        return context


class SuiviCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Suivi
    form_class = SuiviForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("suivis:liste")

    def form_valid(self, form):
        messages.success(self.request, "Suivi enregistré.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouveau suivi"
        context["retour_url"] = self.success_url
        return context


class SuiviUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Suivi
    form_class = SuiviForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("suivis:liste")
    institution_lookup = "beneficiaire__institution"

    def form_valid(self, form):
        messages.success(self.request, "Suivi mis à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        return context
