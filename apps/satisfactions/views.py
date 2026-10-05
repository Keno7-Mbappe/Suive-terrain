from django.contrib import messages
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import SatisfactionForm, SatisfactionInstitutionForm
from .models import AMELIORATIONS_EMPLOYABILITE, UTILITE_DISPOSITIF, Satisfaction, SatisfactionInstitution


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
        queryset = super().get_queryset().select_related("beneficiaire", "beneficiaire__institution", "cycle")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_cycle = self.request.GET.get("cycle", "")
        self.filtre_employabilite = self.request.GET.get("employabilite", "")
        self.filtre_recommande = self.request.GET.get("recommande", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        for mot in self.recherche.split():
            queryset = queryset.filter(Q(beneficiaire__nom__icontains=mot) | Q(beneficiaire__prenom__icontains=mot))
        if self.filtre_cycle:
            queryset = queryset.filter(cycle_id=self.filtre_cycle)
        if self.filtre_employabilite:
            queryset = queryset.filter(amelioration_employabilite=self.filtre_employabilite)
        if self.filtre_recommande:
            queryset = queryset.filter(recommande=(self.filtre_recommande == "oui"))
        if self.filtre_institution:
            queryset = queryset.filter(beneficiaire__institution_id=self.filtre_institution)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = super().get_queryset()
        context["note_moyenne"] = _note_moyenne(self.get_queryset(), CHAMPS_NOTES_BENEFICIAIRE)
        context["recherche"] = self.recherche
        context["filtre_cycle"] = self.filtre_cycle
        context["filtre_employabilite"] = self.filtre_employabilite
        context["filtre_recommande"] = self.filtre_recommande
        context["filtre_institution"] = self.filtre_institution
        context["ameliorations"] = AMELIORATIONS_EMPLOYABILITE
        context["cycles"] = (
            toutes.order_by("-cycle__date_debut").values_list("cycle_id", "cycle__libelle").distinct()
        )
        context["institutions"] = (
            toutes.order_by("beneficiaire__institution__libelle")
            .values_list("beneficiaire__institution_id", "beneficiaire__institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(
            self.recherche or self.filtre_cycle or self.filtre_employabilite
            or self.filtre_recommande or self.filtre_institution
        )
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
        queryset = super().get_queryset().select_related("institution", "cycle")
        self.filtre_cycle = self.request.GET.get("cycle", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        self.filtre_utilite = self.request.GET.get("utilite", "")
        if self.filtre_cycle:
            queryset = queryset.filter(cycle_id=self.filtre_cycle)
        if self.filtre_institution:
            queryset = queryset.filter(institution_id=self.filtre_institution)
        if self.filtre_utilite:
            queryset = queryset.filter(utilite_dispositif=self.filtre_utilite)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = super().get_queryset()
        context["note_moyenne"] = _note_moyenne(self.get_queryset(), CHAMPS_NOTES_INSTITUTION)
        context["filtre_cycle"] = self.filtre_cycle
        context["filtre_institution"] = self.filtre_institution
        context["filtre_utilite"] = self.filtre_utilite
        context["utilites"] = UTILITE_DISPOSITIF
        context["cycles"] = (
            toutes.order_by("-cycle__date_debut").values_list("cycle_id", "cycle__libelle").distinct()
        )
        context["institutions"] = (
            toutes.order_by("institution__libelle").values_list("institution_id", "institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(self.filtre_cycle or self.filtre_institution or self.filtre_utilite)
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
