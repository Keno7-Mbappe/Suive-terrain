"""Met à jour, dans le formulaire Kobo « suivi et satisfaction » déjà déployé, la
liste des bénéficiaires proposée aux enquêteurs (avec le rappel nom / institution /
région / fin de formation / téléphone), à partir de la base de l'application.

Ce formulaire embarque sa liste de bénéficiaires dans sa définition : tant qu'elle
n'est pas republiée, les enquêteurs voient les personnes de la dernière publication
(et, pire, des identifiants qui ne désignent plus les mêmes personnes en base). À
relancer après chaque import de bénéficiaires (nouvelle institution, nouvelle
vague d'inscriptions).

Avant toute modification, la définition actuelle du formulaire est sauvegardée dans
kobo_forms/sauvegardes/ (dossier ignoré par Git) pour pouvoir revenir en arrière.
"""

import json
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.imports.kobo_beneficiaires import lignes_beneficiaires

LISTE_BENEFICIAIRES = "beneficiaire"
TIMEOUT = 60


class Command(BaseCommand):
    help = "Republie la liste des bénéficiaires de la base dans le formulaire Kobo déployé."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait publié, sans rien modifier.")

    def handle(self, *args, **options):
        if not settings.KOBO_API_TOKEN or not settings.KOBO_ASSET_UID_SUIVI:
            raise CommandError("KOBO_API_TOKEN et KOBO_ASSET_UID_SUIVI doivent être renseignés dans .env.")

        base = settings.KOBO_API_BASE_URL.rstrip("/")
        asset_url = f"{base}/api/v2/assets/{settings.KOBO_ASSET_UID_SUIVI}/"
        headers = {"Authorization": f"Token {settings.KOBO_API_TOKEN}"}

        reponse = requests.get(asset_url, headers=headers, params={"format": "json"}, timeout=TIMEOUT)
        reponse.raise_for_status()
        asset = reponse.json()
        contenu = asset["content"]

        lignes = lignes_beneficiaires()
        if not lignes:
            raise CommandError("Aucun bénéficiaire en base : publier une liste vide casserait le formulaire.")

        anciens = [c for c in contenu["choices"] if c.get("list_name") == LISTE_BENEFICIAIRES]
        nouveaux = [
            {
                "list_name": LISTE_BENEFICIAIRES,
                "name": ligne["name"],
                "label": [ligne["label"]],
                **{cle: ligne[cle] for cle in ("nom_prenom", "institution", "region", "date_fin_formation", "telephone")},
            }
            for ligne in lignes
        ]
        self.stdout.write(f"Liste actuelle du formulaire : {len(anciens)} bénéficiaire(s).")
        self.stdout.write(f"Liste à publier (base) : {len(nouveaux)} bénéficiaire(s).")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run : rien n'a été modifié."))
            return

        sauvegarde = self._sauvegarder(asset)
        self.stdout.write(f"Définition actuelle sauvegardée : {sauvegarde}")

        contenu["choices"] = [c for c in contenu["choices"] if c.get("list_name") != LISTE_BENEFICIAIRES] + nouveaux
        reponse = requests.patch(asset_url, headers=headers, json={"content": contenu}, timeout=TIMEOUT)
        if not reponse.ok:
            raise CommandError(f"Kobo a refusé la mise à jour ({reponse.status_code}) : {reponse.text[:500]}")
        version_id = reponse.json()["version_id"]

        reponse = requests.patch(
            f"{asset_url}deployment/", headers=headers, json={"active": True, "version_id": version_id},
            timeout=TIMEOUT,
        )
        if not reponse.ok:
            raise CommandError(
                f"Liste enregistrée (brouillon) mais redéploiement refusé ({reponse.status_code}) : {reponse.text[:500]}"
            )
        self.stdout.write(self.style.SUCCESS(
            f"Formulaire redéployé (version {version_id}) : {len(nouveaux)} bénéficiaire(s) proposés aux enquêteurs."
        ))

    def _sauvegarder(self, asset):
        dossier = Path(settings.BASE_DIR) / "kobo_forms" / "sauvegardes"
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{asset['uid']}_{datetime.now():%Y%m%d_%H%M%S}.json"
        chemin.write_text(json.dumps(asset, ensure_ascii=False, indent=1), encoding="utf-8")
        return chemin
