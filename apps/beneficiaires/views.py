from django.contrib import messages
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import BeneficiaireForm
from .models import Beneficiaire


class BeneficiaireListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Beneficiaire
    template_name = "beneficiaires/liste.html"
    context_object_name = "beneficiaires"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        population = self.get_queryset()
        context["nb_actifs"] = population.filter(statut="actif").count()
        repartition_sexe = dict(population.values_list("sexe").annotate(total=Count("id_beneficiaire")))
        context["nb_femmes"] = repartition_sexe.get("F", 0)
        context["nb_hommes"] = repartition_sexe.get("M", 0)
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
        return context
