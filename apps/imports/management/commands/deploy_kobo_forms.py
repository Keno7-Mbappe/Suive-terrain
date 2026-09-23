"""Cree et deploie les 3 projets KoboToolbox a partir des XLSForm generes
localement (kobo_forms/*.xlsx), directement via l'API Kobo v2 - sans passer
par l'interface web "New > Upload XLSForm".

Flux (confirme sur le code source de kobotoolbox/kpi, cote serveur) :
1. POST /api/v2/imports/ (multipart, avec library=false pour creer un projet
   et non un element de bibliotheque) -> tache d'import asynchrone.
2. Poll GET /api/v2/imports/{uid}/ jusqu'a status="complete" ->
   messages.created[0].uid donne l'UID du nouvel asset (projet, encore en
   brouillon/non deploye a ce stade).
3. Televerse les CSV de listes de choix necessaires comme "form_media" sur
   cet asset (POST /api/v2/assets/{uid}/files/), AVANT le deploiement, pour
   que les questions select_one_from_file trouvent leur fichier.
4. POST /api/v2/assets/{uid}/deployment/ avec {"active": true} -> publie le
   projet, qui peut alors recevoir des soumissions.

A la fin, affiche les 3 UID obtenus a reporter dans .env
(KOBO_ASSET_UID_SUIVI, KOBO_ASSET_UID_SATISFACTION,
KOBO_ASSET_UID_SATISFACTION_INSTITUTION) - et les enregistre lui-meme dans ce
fichier si celui-ci existe a la racine du projet.
"""

import time
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

FORMULAIRES = [
    ("suivi.xlsx", "Suivi longitudinal", "KOBO_ASSET_UID_SUIVI", ["beneficiaires.csv"]),
    (
        "satisfaction_beneficiaire.xlsx", "Satisfaction bénéficiaire", "KOBO_ASSET_UID_SATISFACTION",
        ["beneficiaires.csv", "cycles.csv"],
    ),
    (
        "satisfaction_institution.xlsx", "Satisfaction institutionnelle", "KOBO_ASSET_UID_SATISFACTION_INSTITUTION",
        ["institutions.csv", "cycles.csv"],
    ),
]

TIMEOUT_IMPORT_SECONDES = 60


class Command(BaseCommand):
    help = "Cree et deploie les 3 formulaires Kobo via l'API, a partir de kobo_forms/*.xlsx."

    def handle(self, *args, **options):
        if not settings.KOBO_API_TOKEN:
            raise CommandError(
                "KOBO_API_TOKEN n'est pas renseigné dans .env - impossible d'appeler l'API Kobo."
            )

        self.base_url = settings.KOBO_API_BASE_URL.rstrip("/")
        self.headers = {"Authorization": f"Token {settings.KOBO_API_TOKEN}"}
        self.dossier = Path(settings.BASE_DIR) / "kobo_forms"

        # Verifie que le jeton est valide avant de lancer quoi que ce soit.
        verif = requests.get(f"{self.base_url}/api/v2/assets/", headers=self.headers, timeout=30)
        if verif.status_code == 401:
            raise CommandError("Jeton API Kobo refusé (401) - vérifier KOBO_API_TOKEN et KOBO_API_BASE_URL.")
        verif.raise_for_status()
        self.stdout.write(self.style.SUCCESS(f"Connexion à {self.base_url} OK."))

        resultats = {}
        echecs = []
        for nom_fichier, libelle, env_var, medias in FORMULAIRES:
            try:
                asset_uid = self._deployer_un_formulaire(nom_fichier, libelle, medias)
                resultats[env_var] = asset_uid
            except Exception as exc:  # noqa: BLE001 - on veut continuer avec les formulaires suivants
                self.stderr.write(self.style.ERROR(f"{nom_fichier} : échec - {exc}"))
                echecs.append(nom_fichier)

        if resultats:
            self.stdout.write("\nUID d'assets obtenus :")
            for env_var, uid in resultats.items():
                self.stdout.write(f"  {env_var}={uid}")
            self._mettre_a_jour_env(resultats)

        if echecs:
            raise CommandError(f"{len(echecs)} formulaire(s) non déployé(s) : {', '.join(echecs)}")

    def _deployer_un_formulaire(self, nom_fichier, libelle, medias):
        chemin = self.dossier / nom_fichier
        if not chemin.exists():
            raise CommandError(f"{chemin} introuvable - lancer generate_kobo_xlsforms d'abord.")

        self.stdout.write(f"\n{libelle} ({nom_fichier})")
        self.stdout.write("  Import du XLSForm...")
        with open(chemin, "rb") as f:
            reponse = requests.post(
                f"{self.base_url}/api/v2/imports/",
                headers=self.headers,
                data={"library": "false", "name": nom_fichier},
                files={"file": (nom_fichier, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                timeout=TIMEOUT_IMPORT_SECONDES,
            )
        reponse.raise_for_status()
        import_uid = reponse.json()["uid"]

        asset_uid = self._attendre_import(import_uid, nom_fichier)
        self.stdout.write(f"  Projet créé : {asset_uid}")

        for media in medias:
            self._televerser_media(asset_uid, media)

        self.stdout.write("  Déploiement...")
        reponse = requests.post(
            f"{self.base_url}/api/v2/assets/{asset_uid}/deployment/",
            headers=self.headers, json={"active": True}, timeout=TIMEOUT_IMPORT_SECONDES,
        )
        reponse.raise_for_status()
        self.stdout.write(self.style.SUCCESS(f"  {nom_fichier} déployé (asset {asset_uid})."))
        return asset_uid

    def _attendre_import(self, import_uid, nom_fichier):
        url = f"{self.base_url}/api/v2/imports/{import_uid}/"
        for _ in range(30):
            time.sleep(2)
            statut = requests.get(url, headers=self.headers, timeout=30).json()
            if statut.get("status") == "complete":
                crees = (statut.get("messages") or {}).get("created") or []
                if not crees:
                    raise CommandError(
                        f"Import de {nom_fichier} terminé mais aucun projet créé (destination déjà "
                        f"existante ?) : {statut.get('messages')}"
                    )
                return crees[0]["uid"]
            if statut.get("status") == "error":
                raise CommandError(f"Import de {nom_fichier} en erreur : {statut.get('messages')}")
        raise CommandError(f"Import de {nom_fichier} : délai d'attente dépassé.")

    def _televerser_media(self, asset_uid, nom_media):
        chemin_media = self.dossier / "media" / nom_media
        if not chemin_media.exists():
            raise CommandError(f"{chemin_media} introuvable - lancer export_kobo_choices d'abord.")
        with open(chemin_media, "rb") as f:
            reponse = requests.post(
                f"{self.base_url}/api/v2/assets/{asset_uid}/files/",
                headers=self.headers,
                # "metadata.filename" est exigé par le serializer cote Kobo (sans lui,
                # leur code plante avec une 500 au lieu d'un 400 - vu en pratique).
                data={"description": nom_media, "file_type": "form_media", "metadata": f'{{"filename": "{nom_media}"}}'},
                files={"content": (nom_media, f, "text/csv")},
                timeout=TIMEOUT_IMPORT_SECONDES,
            )
        reponse.raise_for_status()
        self.stdout.write(f"  Media téléversé : {nom_media}")

    def _mettre_a_jour_env(self, resultats):
        chemin_env = Path(settings.BASE_DIR) / ".env"
        if not chemin_env.exists():
            self.stdout.write(self.style.WARNING("Pas de .env trouvé - à renseigner manuellement."))
            return
        lignes = chemin_env.read_text(encoding="utf-8").splitlines()
        for env_var, uid in resultats.items():
            trouve = False
            for i, ligne in enumerate(lignes):
                if ligne.startswith(f"{env_var}="):
                    lignes[i] = f"{env_var}={uid}"
                    trouve = True
                    break
            if not trouve:
                lignes.append(f"{env_var}={uid}")
        chemin_env.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(".env mis à jour."))
