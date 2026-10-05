from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import SuiviForm
from .models import ISSUES_CONTACT, SITUATIONS_ACTUELLES, VAGUES, Suivi


class SuiviListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Suivi
    template_name = "suivis/liste.html"
    context_object_name = "suivis"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("beneficiaire", "beneficiaire__institution")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_vague = self.request.GET.get("vague", "")
        self.filtre_issue = self.request.GET.get("issue", "")
        self.filtre_situation = self.request.GET.get("situation", "")
        self.filtre_institution = self.request.GET.get("institution", "")
        for mot in self.recherche.split():
            queryset = queryset.filter(Q(beneficiaire__nom__icontains=mot) | Q(beneficiaire__prenom__icontains=mot))
        if self.filtre_vague:
            queryset = queryset.filter(vague=self.filtre_vague)
        if self.filtre_issue:
            queryset = queryset.filter(issue_contact=self.filtre_issue)
        if self.filtre_situation:
            queryset = queryset.filter(situation_actuelle=self.filtre_situation)
        if self.filtre_institution:
            queryset = queryset.filter(beneficiaire__institution_id=self.filtre_institution)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = super().get_queryset()
        queryset = self.get_queryset()
        total = queryset.count()
        joints = queryset.filter(issue_contact="joint").count()
        context["nb_joints"] = joints
        context["taux_joignabilite"] = round(joints / total * 100, 1) if total else 0
        context["recherche"] = self.recherche
        context["filtre_vague"] = self.filtre_vague
        context["filtre_issue"] = self.filtre_issue
        context["filtre_situation"] = self.filtre_situation
        context["filtre_institution"] = self.filtre_institution
        context["vagues"] = VAGUES
        context["issues"] = ISSUES_CONTACT
        context["situations"] = SITUATIONS_ACTUELLES
        context["institutions"] = (
            toutes.order_by("beneficiaire__institution__libelle")
            .values_list("beneficiaire__institution_id", "beneficiaire__institution__libelle").distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(
            self.recherche or self.filtre_vague or self.filtre_issue
            or self.filtre_situation or self.filtre_institution
        )
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
        context["supprimer_url"] = reverse("suivis:supprimer", args=[self.object.pk])
        context["supprimer_confirmation"] = f"Supprimer définitivement ce suivi ({self.object}) ?"
        return context


class SuiviSupprimerView(RoleRequiredMixin, View):
    allowed_roles = ("saisie", "validateur")

    def post(self, request, pk):
        queryset = Suivi.objects.all()
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.institution_id is not None:
            queryset = queryset.filter(beneficiaire__institution_id=profile.institution_id)
        suivi = get_object_or_404(queryset, pk=pk)
        reference = str(suivi)
        suivi.delete()
        messages.success(request, f"Suivi « {reference} » supprimé.")
        return redirect("suivis:liste")
