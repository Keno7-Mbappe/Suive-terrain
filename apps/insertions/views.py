from django.contrib import messages
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comptes.mixins import InstitutionScopedFormMixin, InstitutionScopedQuerysetMixin, RoleRequiredMixin

from .forms import InsertionForm
from .models import Insertion


class InsertionListView(RoleRequiredMixin, InstitutionScopedQuerysetMixin, ListView):
    allowed_roles = ("saisie", "validateur", "consultation")
    model = Insertion
    template_name = "insertions/liste.html"
    context_object_name = "insertions"
    paginate_by = 25
    institution_lookup = "beneficiaire__institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repartition = dict(self.get_queryset().values_list("situation_prof").annotate(total=Count("id")))
        context["nb_emploi"] = repartition.get("emploi_salarie", 0)
        context["nb_auto_emploi"] = repartition.get("auto_emploi", 0)
        context["nb_recherche"] = repartition.get("en_recherche", 0)
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
        return context
