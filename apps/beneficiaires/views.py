from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin
from apps.referentiels.models import REGIONS

from .forms import BeneficiaireForm
from .models import SEXES, STATUTS, Beneficiaire


class BeneficiaireListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Beneficiaire
    template_name = "beneficiaires/liste.html"
    context_object_name = "beneficiaires"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related("institution")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_sexe = self.request.GET.get("sexe", "")
        self.filtre_region = self.request.GET.get("region", "")
        self.filtre_niveau_etude = self.request.GET.get("niveau_etude", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        self.filtre_statut = self.request.GET.get("statut", "")
        # Chaque mot doit correspondre au nom OU au prénom, pour retrouver un bénéficiaire
        # en tapant "nom prénom" ou "prénom nom" indifféremment.
        for mot in self.recherche.split():
            queryset = queryset.filter(Q(nom__icontains=mot) | Q(prenom__icontains=mot))
        if self.filtre_sexe:
            queryset = queryset.filter(sexe=self.filtre_sexe)
        if self.filtre_region:
            queryset = queryset.filter(region=self.filtre_region)
        if self.filtre_niveau_etude:
            queryset = queryset.filter(niveau_etude=self.filtre_niveau_etude)
        if self.filtre_institution:
            queryset = queryset.filter(institution_id=self.filtre_institution)
        if self.filtre_statut:
            queryset = queryset.filter(statut=self.filtre_statut)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        population_scope = super().get_queryset()
        population = self.get_queryset()
        context["nb_actifs"] = population.filter(statut="actif").count()
        repartition_sexe = dict(population.values_list("sexe").annotate(total=Count("id_beneficiaire")))
        context["nb_femmes"] = repartition_sexe.get("F", 0)
        context["nb_hommes"] = repartition_sexe.get("M", 0)
        context["recherche"] = self.recherche
        context["filtre_sexe"] = self.filtre_sexe
        context["filtre_region"] = self.filtre_region
        context["filtre_niveau_etude"] = self.filtre_niveau_etude
        context["filtre_institution"] = self.filtre_institution
        context["filtre_statut"] = self.filtre_statut
        context["sexes"] = SEXES
        context["regions"] = REGIONS
        context["statuts"] = STATUTS
        context["niveaux_etude"] = (
            population_scope.exclude(niveau_etude="")
            .order_by("niveau_etude").values_list("niveau_etude", flat=True).distinct()
        )
        context["institutions"] = (
            population_scope.order_by("institution__libelle")
            .values_list("institution_id", "institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(
            self.recherche or self.filtre_sexe or self.filtre_region
            or self.filtre_niveau_etude or self.filtre_institution or self.filtre_statut
        )
        return context


class BeneficiaireCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Beneficiaire
    form_class = BeneficiaireForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("beneficiaires:liste")

    def form_valid(self, form):
        messages.success(self.request, "Bénéficiaire enregistré.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouveau bénéficiaire"
        context["retour_url"] = self.success_url
        return context


class BeneficiaireUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Beneficiaire
    form_class = BeneficiaireForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("beneficiaires:liste")

    def form_valid(self, form):
        messages.success(self.request, "Bénéficiaire mis à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        context["supprimer_url"] = reverse("beneficiaires:supprimer", args=[self.object.pk])
        context["supprimer_confirmation"] = (
            f"Supprimer définitivement {self.object} ? Toutes ses données liées (formations, suivis, "
            "satisfaction, insertions, certifications) seront supprimées aussi. Cette action est irréversible."
        )
        return context


class BeneficiaireSupprimerView(RoleRequiredMixin, View):
    allowed_roles = ("saisie", "validateur")

    def post(self, request, pk):
        queryset = Beneficiaire.objects.all()
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.institution_id is not None:
            queryset = queryset.filter(institution_id=profile.institution_id)
        beneficiaire = get_object_or_404(queryset, pk=pk)
        reference = str(beneficiaire)
        beneficiaire.delete()
        messages.success(request, f"{reference} supprimé, avec toutes ses données liées.")
        return redirect("beneficiaires:liste")
