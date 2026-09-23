from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.comptes.mixins import RoleRequiredMixin

from .models import STATUTS_TRAITEMENT, TYPES_FORMULAIRE, KoboSoumission
from .services import traiter_soumission


class SoumissionListView(RoleRequiredMixin, ListView):
    """Page de contrôle des questionnaires Kobo : permet à un validateur de
    revoir les soumissions brutes, en particulier celles en erreur, sans
    passer par l'admin Django."""

    allowed_roles = ("validateur",)
    model = KoboSoumission
    template_name = "imports/liste.html"
    context_object_name = "soumissions"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        self.filtre_statut = self.request.GET.get("statut", "")
        self.filtre_type = self.request.GET.get("type", "")
        if self.filtre_statut:
            queryset = queryset.filter(statut=self.filtre_statut)
        if self.filtre_type:
            queryset = queryset.filter(type_formulaire=self.filtre_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        toutes = KoboSoumission.objects.all()
        context["statuts"] = STATUTS_TRAITEMENT
        context["types_formulaire"] = TYPES_FORMULAIRE
        context["filtre_statut"] = self.filtre_statut
        context["filtre_type"] = self.filtre_type
        context["nb_total"] = toutes.count()
        context["nb_nouveau"] = toutes.filter(statut="nouveau").count()
        context["nb_erreur"] = toutes.filter(statut="erreur").count()
        context["nb_integre"] = toutes.filter(statut="integre").count()
        return context


class SoumissionReessayerView(RoleRequiredMixin, View):
    allowed_roles = ("validateur",)

    def post(self, request, pk):
        soumission = get_object_or_404(KoboSoumission, pk=pk)
        if traiter_soumission(soumission):
            messages.success(request, f"Soumission {soumission.kobo_submission_id} intégrée avec succès.")
        else:
            messages.error(request, f"Échec de l'intégration : {soumission.erreur}")
        return redirect(request.POST.get("next") or reverse("imports:liste"))


class SoumissionMarquerDoublonView(RoleRequiredMixin, View):
    allowed_roles = ("validateur",)

    def post(self, request, pk):
        soumission = get_object_or_404(KoboSoumission, pk=pk)
        soumission.statut = "doublon"
        soumission.erreur = ""
        soumission.traite_le = timezone.now()
        soumission.save(update_fields=["statut", "erreur", "traite_le"])
        messages.success(request, f"Soumission {soumission.kobo_submission_id} marquée comme doublon et écartée.")
        return redirect(request.POST.get("next") or reverse("imports:liste"))
