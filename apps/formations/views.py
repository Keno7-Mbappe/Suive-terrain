from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import FormationForm
from .models import STATUTS_FORMATION, Formation


class FormationListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Formation
    template_name = "formations/liste.html"
    context_object_name = "formations"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("beneficiaire", "beneficiaire__institution")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_domaine = self.request.GET.get("domaine", "")
        self.filtre_centre = self.request.GET.get("centre", "")
        self.filtre_statut = self.request.GET.get("statut", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        # Chaque mot doit correspondre au domaine ou au nom/prénom du bénéficiaire, pour
        # retrouver une formation en tapant le nom de la personne ou celui de la filière.
        for mot in self.recherche.split():
            queryset = queryset.filter(
                Q(domaine__icontains=mot) | Q(beneficiaire__nom__icontains=mot) | Q(beneficiaire__prenom__icontains=mot)
            )
        if self.filtre_domaine:
            queryset = queryset.filter(domaine=self.filtre_domaine)
        if self.filtre_centre:
            queryset = queryset.filter(centre=self.filtre_centre)
        if self.filtre_statut:
            queryset = queryset.filter(statut_formation=self.filtre_statut)
        if self.filtre_institution:
            queryset = queryset.filter(beneficiaire__institution_id=self.filtre_institution)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = super().get_queryset()
        repartition = dict(self.get_queryset().values_list("statut_formation").annotate(total=Count("id")))
        context["nb_achevees"] = repartition.get("achevee", 0)
        context["nb_en_cours"] = repartition.get("en_cours", 0)
        context["nb_abandonnees"] = repartition.get("abandonnee", 0)
        context["recherche"] = self.recherche
        context["filtre_domaine"] = self.filtre_domaine
        context["filtre_centre"] = self.filtre_centre
        context["filtre_statut"] = self.filtre_statut
        context["filtre_institution"] = self.filtre_institution
        context["statuts"] = STATUTS_FORMATION
        context["domaines"] = toutes.exclude(domaine="").order_by("domaine").values_list("domaine", flat=True).distinct()
        context["centres"] = toutes.exclude(centre="").order_by("centre").values_list("centre", flat=True).distinct()
        context["institutions"] = (
            toutes.order_by("beneficiaire__institution__libelle")
            .values_list("beneficiaire__institution_id", "beneficiaire__institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(
            self.recherche or self.filtre_domaine or self.filtre_centre
            or self.filtre_statut or self.filtre_institution
        )
        return context


class FormationCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Formation
    form_class = FormationForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("formations:liste")

    def form_valid(self, form):
        messages.success(self.request, "Formation enregistrée.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouvelle formation"
        context["retour_url"] = self.success_url
        return context


class FormationUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Formation
    form_class = FormationForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("formations:liste")
    institution_lookup = "beneficiaire__institution"

    def form_valid(self, form):
        messages.success(self.request, "Formation mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        return context
