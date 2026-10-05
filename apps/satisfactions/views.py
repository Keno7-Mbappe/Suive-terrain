from django.contrib import messages
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import SatisfactionForm, SatisfactionInstitutionForm
from .models import Satisfaction, SatisfactionInstitution


def _note_moyenne(queryset, champs):
    moyennes = queryset.aggregate(**{champ: Avg(champ) for champ in champs})
    valeurs = [v for v in moyennes.values() if v is not None]
    return round(sum(valeurs) / len(valeurs), 2) if valeurs else None


CHAMPS_NOTES_BENEFICIAIRE = ["note_formation", "note_formateurs", "note_contenus", "note_equipements", "note_accueil"]
CHAMPS_NOTES_INSTITUTION = [
    "note_qualite_donnees", "note_outils_collecte", "note_tableaux_bord",
    "note_appui_technique", "note_coordination",
]


class SatisfactionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Satisfaction
    template_name = "satisfactions/liste.html"
    context_object_name = "satisfactions"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_queryset(self):
        return super().get_queryset().select_related("beneficiaire", "cycle")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["note_moyenne"] = _note_moyenne(self.get_queryset(), CHAMPS_NOTES_BENEFICIAIRE)
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
        context["supprimer_url"] = reverse("satisfactions:supprimer", args=[self.object.pk])
        context["supprimer_confirmation"] = f"Supprimer définitivement cette réponse de satisfaction ({self.object}) ?"
        return context


class SatisfactionSupprimerView(RoleRequiredMixin, View):
    allowed_roles = ("saisie", "validateur")

    def post(self, request, pk):
        queryset = Satisfaction.objects.all()
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.institution_id is not None:
            queryset = queryset.filter(beneficiaire__institution_id=profile.institution_id)
        satisfaction = get_object_or_404(queryset, pk=pk)
        reference = str(satisfaction)
        satisfaction.delete()
        messages.success(request, f"Réponse de satisfaction « {reference} » supprimée.")
        return redirect("satisfactions:liste")


class SatisfactionInstitutionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = SatisfactionInstitution
    template_name = "satisfactions/liste_institution.html"
    context_object_name = "satisfactions"
    paginate_by = 25
    institution_lookup = "institution"

    def get_queryset(self):
        return super().get_queryset().select_related("institution", "cycle")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["note_moyenne"] = _note_moyenne(self.get_queryset(), CHAMPS_NOTES_INSTITUTION)
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
        context["supprimer_url"] = reverse("satisfactions:supprimer_institution", args=[self.object.pk])
        context["supprimer_confirmation"] = f"Supprimer définitivement cette satisfaction institutionnelle ({self.object}) ?"
        return context


class SatisfactionInstitutionSupprimerView(RoleRequiredMixin, View):
    allowed_roles = ("saisie", "validateur")

    def post(self, request, pk):
        queryset = SatisfactionInstitution.objects.all()
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.institution_id is not None:
            queryset = queryset.filter(institution_id=profile.institution_id)
        satisfaction = get_object_or_404(queryset, pk=pk)
        reference = str(satisfaction)
        satisfaction.delete()
        messages.success(request, f"Satisfaction institutionnelle « {reference} » supprimée.")
        return redirect("satisfactions:liste_institution")
