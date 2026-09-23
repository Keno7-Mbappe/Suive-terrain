from django.contrib import messages
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import FormationForm
from .models import Formation


class FormationListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Formation
    template_name = "formations/liste.html"
    context_object_name = "formations"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repartition = dict(self.get_queryset().values_list("statut_formation").annotate(total=Count("id")))
        context["nb_achevees"] = repartition.get("achevee", 0)
        context["nb_en_cours"] = repartition.get("en_cours", 0)
        context["nb_abandonnees"] = repartition.get("abandonnee", 0)
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
