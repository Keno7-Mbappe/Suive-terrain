"""Ajoute au formulaire Kobo « suivi et satisfaction » déjà déployé les nouvelles
questions réfugié / situation de handicap / détails de stage (structure d'accueil,
encadrant, date de fin), sans toucher au reste du formulaire (liste des
bénéficiaires, questions existantes) ni créer un nouveau projet Kobo.

Insère les nouvelles lignes directement dans le groupe "module_suivi" déjà présent
sur l'asset déployé (avant sa fin), et ajoute les listes de choix "pays_origine"
et "type_handicap" - suit le même schéma JSON (content.survey / content.choices)
que celui produit par l'API Kobo, confirmé par lecture de l'asset réel, et le même
mécanisme éprouvé que `publier_beneficiaires_kobo` (PATCH content -> version_id ->
PATCH deployment).

Avant toute modification, la définition actuelle du formulaire est sauvegardée dans
kobo_forms/sauvegardes/ (dossier ignoré par Git) pour pouvoir revenir en arrière.
"""

import json
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.beneficiaires.models import PAYS_ORIGINE_REFUGIE, TYPES_HANDICAP

TIMEOUT = 60

NOUVELLES_LIGNES_SURVEY = [
    {"name": "structure_accueil", "type": "text", "label": ["Structure d'accueil du stage"],
     "required": True, "relevant": "selected(${situation}, 'stage')"},
    {"name": "nom_encadrant", "type": "text", "label": ["Nom de l'encadrant / maître de stage"],
     "relevant": "selected(${situation}, 'stage')"},
    {"name": "date_fin_stage", "type": "date", "label": ["Date de fin de stage prévue"],
     "relevant": "selected(${situation}, 'stage')"},
    {"name": "consigne_profil", "type": "note",
     "label": ["Les deux questions suivantes mettent à jour la fiche du bénéficiaire (utile si ce n'était pas "
               "connu à l'inscription) - répondez-y seulement si vous avez l'information."]},
    {"name": "refugie", "type": "select_one", "select_from_list_name": "oui_non",
     "label": ["Le/la bénéficiaire est-il/elle réfugié(e) ?"]},
    {"name": "pays_origine", "type": "select_one", "select_from_list_name": "pays_origine",
     "label": ["Pays d'origine"], "required": True, "relevant": "selected(${refugie}, 'oui')"},
    {"name": "handicap", "type": "select_one", "select_from_list_name": "oui_non",
     "label": ["Le/la bénéficiaire est-il/elle en situation de handicap ?"]},
    {"name": "type_handicap", "type": "select_one", "select_from_list_name": "type_handicap",
     "label": ["Type de handicap"], "required": True, "relevant": "selected(${handicap}, 'oui')"},
]

NOMS_NOUVELLES_LIGNES = {ligne["name"] for ligne in NOUVELLES_LIGNES_SURVEY}

NOUVELLES_LISTES_CHOIX = {
    "pays_origine": PAYS_ORIGINE_REFUGIE,
    "type_handicap": TYPES_HANDICAP,
}


class Command(BaseCommand):
    help = "Ajoute les questions réfugié/handicap/stage au formulaire Kobo 'suivi' déjà déployé."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait modifié, sans rien publier.")

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
        survey = contenu["survey"]

        noms_existants = {row.get("name") for row in survey}
        deja_present = NOMS_NOUVELLES_LIGNES & noms_existants
        if deja_present:
            raise CommandError(
                f"Ces champs existent déjà dans le formulaire déployé : {sorted(deja_present)} - "
                "la commande a peut-être déjà été exécutée. Rien n'a été modifié."
            )

        index_fin_module_suivi = next(
            (i for i, row in enumerate(survey) if row.get("type") == "end_group" and row.get("name") == "module_suivi"),
            None,
        )
        if index_fin_module_suivi is None:
            raise CommandError("Groupe 'module_suivi' introuvable dans le formulaire déployé - structure inattendue.")

        self.stdout.write(f"Formulaire actuel : {len(survey)} ligne(s), {len(contenu['choices'])} choix.")
        self.stdout.write(f"{len(NOUVELLES_LIGNES_SURVEY)} nouvelle(s) question(s) seront insérées dans 'module_suivi'.")
        for liste, options_liste in NOUVELLES_LISTES_CHOIX.items():
            self.stdout.write(f"Nouvelle liste de choix '{liste}' : {len(options_liste)} option(s).")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run : rien n'a été modifié."))
            return

        sauvegarde = self._sauvegarder(asset)
        self.stdout.write(f"Définition actuelle sauvegardée : {sauvegarde}")

        nouveau_survey = survey[:index_fin_module_suivi] + NOUVELLES_LIGNES_SURVEY + survey[index_fin_module_suivi:]
        nouveaux_choix = list(contenu["choices"])
        for list_name, options_liste in NOUVELLES_LISTES_CHOIX.items():
            for name, label in options_liste:
                nouveaux_choix.append({"list_name": list_name, "name": name, "label": [label]})

        contenu["survey"] = nouveau_survey
        contenu["choices"] = nouveaux_choix

        reponse = requests.patch(asset_url, headers=headers, json={"content": contenu}, timeout=TIMEOUT)
        if not reponse.ok:
            raise CommandError(f"Kobo a refusé la mise à jour ({reponse.status_code}) : {reponse.text[:800]}")
        version_id = reponse.json()["version_id"]

        reponse = requests.patch(
            f"{asset_url}deployment/", headers=headers, json={"active": True, "version_id": version_id},
            timeout=TIMEOUT,
        )
        if not reponse.ok:
            raise CommandError(
                f"Formulaire enregistré (brouillon, version {version_id}) mais redéploiement refusé "
                f"({reponse.status_code}) : {reponse.text[:800]}"
            )
        self.stdout.write(self.style.SUCCESS(
            f"Formulaire redéployé (version {version_id}) : {len(NOUVELLES_LIGNES_SURVEY)} question(s) ajoutée(s)."
        ))

    def _sauvegarder(self, asset):
        dossier = Path(settings.BASE_DIR) / "kobo_forms" / "sauvegardes"
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{asset['uid']}_{datetime.now():%Y%m%d_%H%M%S}.json"
        chemin.write_text(json.dumps(asset, ensure_ascii=False, indent=1), encoding="utf-8")
        return chemin
