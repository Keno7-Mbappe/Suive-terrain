from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.comptes.mixins import RoleRequiredMixin
from apps.referentiels.models import CycleEnquete

from .services import generer_rapport_cycle


class RapportsIndexView(RoleRequiredMixin, View):
    allowed_roles = ("validateur", "consultation")

    def get(self, request):
        return render(request, "reporting/index.html", {"cycles": CycleEnquete.objects.all()})


class RapportCycleExcelView(RoleRequiredMixin, View):
    allowed_roles = ("validateur",)

    def get(self, request, pk):
        cycle = get_object_or_404(CycleEnquete, pk=pk)
        profile = getattr(request.user, "profile", None)
        institution_id = profile.institution_id if profile else None

        classeur = generer_rapport_cycle(cycle, institution_id=institution_id)
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        nom_fichier = f"rapport_{cycle.libelle.replace(' ', '_')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
        classeur.save(response)
        return response
