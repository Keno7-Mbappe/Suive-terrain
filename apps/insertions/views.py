from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import InsertionForm
from .models import SITUATIONS_PRO, Insertion


class InsertionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Insertion
    template_name = "insertions/liste.html"
    context_object_name = "insertions"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("beneficiaire", "beneficiaire__institution")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_situation = self.request.GET.get("situation", "")
        self.filtre_secteur = self.request.GET.get("secteur", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        for mot in self.recherche.split():
            queryset = queryset.filter(Q(beneficiaire__nom__icontains=mot) | Q(beneficiaire__prenom__icontains=mot))
        if self.filtre_situation:
            queryset = queryset.filter(situation_prof=self.filtre_situation)
        if self.filtre_secteur:
            queryset = queryset.filter(secteur_activite=self.filtre_secteur)
        if self.filtre_institution:
            queryset = queryset.filter(beneficiaire__institution_id=self.filtre_institution)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = super().get_queryset()
        repartition = dict(self.get_queryset().values_list("situation_prof").annotate(total=Count("id")))
        context["nb_emploi"] = repartition.get("emploi_salarie", 0)
        context["nb_auto_emploi"] = repartition.get("auto_emploi", 0)
        context["nb_recherche"] = repartition.get("en_recherche", 0)
        context["recherche"] = self.recherche
        context["filtre_situation"] = self.filtre_situation
        context["filtre_secteur"] = self.filtre_secteur
        context["filtre_institution"] = self.filtre_institution
        context["situations"] = SITUATIONS_PRO
        context["secteurs"] = toutes.exclude(secteur_activite="").order_by("secteur_activite").values_list(
            "secteur_activite", flat=True
        ).distinct()
        context["institutions"] = (
            toutes.order_by("beneficiaire__institution__libelle")
            .values_list("beneficiaire__institution_id", "beneficiaire__institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(
            self.recherche or self.filtre_situation or self.filtre_secteur or self.filtre_institution
        )
        return context


class InsertionCreateView(RoleRequiredMixin, InstitutionScopedFormMixin, CreateView):
    allowed_roles = ("saisie",)
    model = Insertion
    form_class = InsertionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("insertions:liste")

    def form_valid(self, form):
        messages.success(self.request, "Insertion enregistrée.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = "Nouvelle insertion"
        context["retour_url"] = self.success_url
        return context


class InsertionUpdateView(RoleRequiredMixin, InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, UpdateView):
    allowed_roles = ("saisie", "validateur")
    model = Insertion
    form_class = InsertionForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("insertions:liste")
    institution_lookup = "beneficiaire__institution"

    def form_valid(self, form):
        messages.success(self.request, "Insertion mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titre"] = f"Modifier {self.object}"
        context["retour_url"] = self.success_url
        context["supprimer_url"] = reverse("insertions:supprimer", args=[self.object.pk])
        context["supprimer_confirmation"] = f"Supprimer définitivement cette insertion ({self.object}) ?"
        return context


class InsertionSupprimerView(RoleRequiredMixin, View):
    allowed_roles = ("saisie", "validateur")

    def post(self, request, pk):
        queryset = Insertion.objects.all()
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.institution_id is not None:
            queryset = queryset.filter(beneficiaire__institution_id=profile.institution_id)
        insertion = get_object_or_404(queryset, pk=pk)
        reference = str(insertion)
        insertion.delete()
        messages.success(request, f"Insertion « {reference} » supprimée.")
        return redirect("insertions:liste")
