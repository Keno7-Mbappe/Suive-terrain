from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.mixins import RoleRequiredMixin

from .forms import SoumissionCorrectionForm
from .models import STATUTS_TRAITEMENT, TYPES_FORMULAIRE, KoboSoumission
from .schemas import METADONNEES, RAPPEL_SUIVI, lignes_lisibles
from .services import controler_soumission, synchroniser_tout, traiter_soumission


class SoumissionScopeeMixin(RoleRequiredMixin):
    """Réservé aux validateurs (et administrateurs) ; un validateur rattaché à une
    institution ne voit que les soumissions de cette institution."""

    allowed_roles = ("validateur",)

    def get_soumission(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    def get_queryset(self):
        return KoboSoumission.objects.select_related("institution", "traite_par").filter(
            **self._filtre_institution()
        )

    def _filtre_institution(self):
        profile = getattr(self.request.user, "profile", None)
        if profile is None or profile.institution_id is None:
            return {}
        return {"institution_id": profile.institution_id}

    def rediriger_apres_action(self, defaut):
        cible = self.request.POST.get("next")
        if cible and url_has_allowed_host_and_scheme(cible, allowed_hosts={self.request.get_host()}):
            return redirect(cible)
        return redirect(defaut)


class SoumissionListView(SoumissionScopeeMixin, ListView):
    """File d'attente de validation des questionnaires Kobo : tout ce qui arrive de
    Kobo attend ici qu'un validateur le relise avant d'entrer dans la base."""

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
        toutes = super().get_queryset()
        context["statuts"] = STATUTS_TRAITEMENT
        context["types_formulaire"] = TYPES_FORMULAIRE
        context["filtre_statut"] = self.filtre_statut
        context["filtre_type"] = self.filtre_type
        context["nb_total"] = toutes.count()
        context["nb_nouveau"] = toutes.filter(statut="nouveau").count()
        context["nb_erreur"] = toutes.filter(statut="erreur").count()
        context["nb_integre"] = toutes.filter(statut="integre").count()
        return context


class SoumissionActualiserView(SoumissionScopeeMixin, View):
    """Va chercher sur Kobo les questionnaires soumis depuis la dernière actualisation
    et les dépose « à valider » (rien n'est intégré à la base à ce stade)."""

    def post(self, request):
        nouvelles = 0
        for resultat in synchroniser_tout():
            if resultat["erreur"]:
                messages.warning(request, f"{resultat['libelle']} : {resultat['erreur']}.")
            nouvelles += resultat["nouvelles"]
        if nouvelles:
            messages.success(request, f"{nouvelles} nouvelle(s) soumission(s) reçue(s) de Kobo, à valider.")
        else:
            messages.info(request, "Aucune nouvelle soumission sur Kobo.")
        return redirect("imports:liste")


class SoumissionDetailView(SoumissionScopeeMixin, View):
    """Lecture complète d'une soumission : le formulaire rempli, en clair, avec les
    points d'attention et les actions possibles (valider, corriger, supprimer)."""

    def get(self, request, pk):
        soumission = self.get_soumission(pk)
        donnees = soumission.donnees_effectives
        beneficiaire = None
        if soumission.type_formulaire == "suivi":
            beneficiaire = Beneficiaire.objects.select_related("institution").filter(
                pk=donnees.get("selection/id_beneficiaire")
            ).first()
        rappel = [
            (libelle, donnees.get(cle)) for cle, libelle in RAPPEL_SUIVI if donnees.get(cle) not in (None, "")
        ] if soumission.type_formulaire == "suivi" else []
        metadonnees = [
            (libelle, donnees.get(cle)) for cle, libelle in METADONNEES if donnees.get(cle) not in (None, "")
        ]
        return render(request, "imports/detail.html", {
            "soumission": soumission,
            "sections": lignes_lisibles(soumission.type_formulaire, donnees),
            "rappel": rappel,
            "metadonnees": metadonnees,
            "beneficiaire": beneficiaire,
            "alertes": controler_soumission(soumission),
            "peut_valider": soumission.statut in ("nouveau", "erreur"),
            "peut_supprimer": soumission.statut != "integre",
        })


class SoumissionCorrigerView(SoumissionScopeeMixin, View):
    template_name = "imports/corriger.html"

    def _rendu(self, request, soumission, form):
        return render(request, self.template_name, {"soumission": soumission, "form": form})

    def get(self, request, pk):
        soumission = self.get_soumission(pk)
        return self._rendu(request, soumission, SoumissionCorrectionForm(soumission=soumission))

    def post(self, request, pk):
        soumission = self.get_soumission(pk)
        form = SoumissionCorrectionForm(request.POST, soumission=soumission)
        if not form.is_valid():
            return self._rendu(request, soumission, form)
        form.enregistrer()
        messages.success(
            request, "Correction enregistrée. Les données reçues de Kobo sont conservées telles quelles ; "
                     "la soumission est à valider avec vos corrections."
        )
        return redirect("imports:detail", pk=soumission.pk)


class SoumissionValiderView(SoumissionScopeeMixin, View):
    """Intègre la version effective de la soumission dans la base (et donc le tableau de bord)."""

    def post(self, request, pk):
        soumission = self.get_soumission(pk)
        if traiter_soumission(soumission, utilisateur=request.user):
            messages.success(request, "Soumission validée : les données sont maintenant dans la base et le tableau de bord.")
        else:
            messages.error(request, f"Validation impossible : {soumission.erreur}")
        return self.rediriger_apres_action(reverse("imports:detail", args=[soumission.pk]))


class SoumissionSupprimerView(SoumissionScopeeMixin, View):
    def post(self, request, pk):
        soumission = self.get_soumission(pk)
        if soumission.statut == "integre":
            messages.error(
                request,
                "Une soumission déjà intégrée ne peut pas être supprimée : les données qu'elle a créées "
                "sont dans la base. Corrigez-la puis validez-la à nouveau si nécessaire.",
            )
            return redirect("imports:detail", pk=soumission.pk)
        reference = str(soumission)
        soumission.delete()
        messages.success(request, f"{reference} supprimée.")
        return redirect("imports:liste")


class SoumissionMarquerDoublonView(SoumissionScopeeMixin, View):
    """Écarte une soumission (doublon, test...) sans la supprimer : elle reste
    consultable et, surtout, n'est pas re-téléchargée depuis Kobo à la prochaine synchro."""

    def post(self, request, pk):
        soumission = self.get_soumission(pk)
        if soumission.statut == "integre":
            messages.error(request, "Une soumission déjà intégrée ne peut pas être écartée.")
            return redirect("imports:detail", pk=soumission.pk)
        soumission.statut = "doublon"
        soumission.erreur = ""
        soumission.traite_le = timezone.now()
        soumission.traite_par = request.user
        soumission.save(update_fields=["statut", "erreur", "traite_le", "traite_par"])
        messages.success(request, f"Soumission {soumission.kobo_submission_id} écartée.")
        return self.rediriger_apres_action(reverse("imports:liste"))


# Conservé sous ce nom : « Réessayer » est le même geste que « Valider » pour une soumission en erreur.
SoumissionReessayerView = SoumissionValiderView
