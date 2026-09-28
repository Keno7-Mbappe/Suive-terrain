"""Liste des bénéficiaires telle que les formulaires Kobo la consomment : un
identifiant (`name`), un libellé lisible pour l'enquêteur, et les informations
de rappel (nom, institution, région, fin de formation, téléphone) affichées
dès la sélection. Source unique pour l'export CSV (`export_kobo_choices`) et la
publication dans le formulaire déployé (`publier_beneficiaires_kobo`)."""

from apps.beneficiaires.models import Beneficiaire


def lignes_beneficiaires():
    lignes = []
    beneficiaires = (
        Beneficiaire.objects.select_related("institution").prefetch_related("formations").order_by("id_beneficiaire")
    )
    for b in beneficiaires:
        derniere_formation = b.formations.first()  # Formation.Meta.ordering = ["-date_debut"]
        date_fin = derniere_formation.date_fin if derniere_formation else None
        nom_prenom = f"{b.prenom} {b.nom}".strip()
        lignes.append({
            "name": b.id_beneficiaire,
            "label": f"{b.id_beneficiaire} – {nom_prenom} ({b.institution.libelle})",
            "nom_prenom": nom_prenom,
            "institution": b.institution.libelle,
            "region": b.get_region_display(),
            "date_fin_formation": date_fin.isoformat() if date_fin else "",
            "telephone": b.telephone,
        })
    return lignes
