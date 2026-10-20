from django.db.models import Q
from django.views.generic import ListView

from apps.comptes.mixins import RoleRequiredMixin

from .models import ACTIONS, Modification


class ModificationListView(RoleRequiredMixin, ListView):
    """Journal des modifications : consultable par les validateurs (et administrateurs,
    toujours autorisés par RoleRequiredMixin), pas par la saisie seule - cf. nav."""

    allowed_roles = ("validateur",)
    model = Modification
    template_name = "journal/liste.html"
    context_object_name = "modifications"
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related("utilisateur")
        self.recherche = self.request.GET.get("q", "").strip()
        self.filtre_modele = self.request.GET.get("modele", "")
        self.filtre_action = self.request.GET.get("action", "")
        if self.recherche:
            queryset = queryset.filter(
                Q(objet_repr__icontains=self.recherche) | Q(objet_id__icontains=self.recherche)
            )
        if self.filtre_modele:
            queryset = queryset.filter(modele=self.filtre_modele)
        if self.filtre_action:
            queryset = queryset.filter(action=self.filtre_action)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recherche"] = self.recherche
        context["filtre_modele"] = self.filtre_modele
        context["filtre_action"] = self.filtre_action
        context["actions"] = ACTIONS
        context["modeles"] = (
            Modification.objects.order_by("modele").values_list("modele", flat=True).distinct()
        )
        querystring = self.request.GET.copy()
        querystring.pop("page", None)
        context["querystring_filtres"] = querystring.urlencode()
        context["filtres_actifs"] = bool(self.recherche or self.filtre_modele or self.filtre_action)
        return context
