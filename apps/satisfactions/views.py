from django.contrib import messages
from django.db.models import Avg
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import SatisfactionForm, SatisfactionInstitutionForm
from .models import Satisfaction, SatisfactionInstitution


def _note_moyenne(queryset):
    moyennes = queryset.aggregate(
        formation=Avg("note_formation"), formateurs=Avg("note_formateurs"), contenus=Avg("note_contenus"),
        equipements=Avg("note_equipements"), accueil=Avg("note_accueil"),
    )
    valeurs = [v for v in moyennes.values() if v is not None]
    return round(sum(valeurs) / len(valeurs), 2) if valeurs else None


class SatisfactionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Satisfaction
    template_name = "satisfactions/liste.html"
    context_object_name = "satisfactions"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["note_moyenne"] = _note_moyenne(self.get_queryset())
        return context


class SatisfactionCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Satisfaction
    form_class = SatisfactionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("satisfactions:liste")

    def form_valid(self, form):
        messages.success(self.request, "Réponse de satisfaction enregistrée.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouvelle réponse de satisfaction"
        context["retour_url"] = self.success_url
        return context


class SatisfactionUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Satisfaction
    form_class = SatisfactionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("satisfactions:liste")
    institution_lookup = "beneficiaire__institution"

    def form_valid(self, form):
        messages.success(self.request, "Réponse de satisfaction mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        return context


class SatisfactionInstitutionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = SatisfactionInstitution
    template_name = "satisfactions/liste_institution.html"
    context_object_name = "satisfactions"
    paginate_by = 25
    institution_lookup = "institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["note_moyenne"] = _note_moyenne(self.get_queryset())
        return context


class SatisfactionInstitutionCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = SatisfactionInstitution
    form_class = SatisfactionInstitutionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("satisfactions:liste_institution")

    def form_valid(self, form):
        messages.success(self.request, "Satisfaction institutionnelle enregistrée.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouvelle satisfaction institutionnelle"
        context["retour_url"] = self.success_url
        return context


class SatisfactionInstitutionUpdateView(
    RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView
):
    allowed_roles = ("saisie", "validateur")
    model = SatisfactionInstitution
    form_class = SatisfactionInstitutionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("satisfactions:liste_institution")
    institution_lookup = "institution"

    def form_valid(self, form):
        messages.success(self.request, "Satisfaction institutionnelle mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        return context
