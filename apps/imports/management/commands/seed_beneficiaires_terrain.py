"""Remplace le jeu de données de démonstration des bénéficiaires par celui du
formulaire Kobo réellement déployé et déjà utilisé sur le terrain
(compte KoboToolbox "raliya", asset "PDCED – Skills | Enquête terrain") : les
20 bénéficiaires ci-dessous sont exactement ceux embarqués dans ce
questionnaire, avec les identifiants B-2026-0001 à B-2026-0020 déjà utilisés
dans ses 4 vraies soumissions.

Sans cet alignement, `manage.py sync_kobo` échoue avec "Bénéficiaire
introuvable" sur toute soumission réelle : nos identifiants générés
localement (import de démonstration précédent) ne correspondaient pas à ceux
attendus par le formulaire déjà en circulation.

Remplace intégralement la table des bénéficiaires (et tout ce qui en dépend
par cascade : formations, certifications, insertions, suivis, satisfactions)
- n'a de sens que tant qu'aucune vraie donnée de production n'existe encore.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.beneficiaires.models import Beneficiaire, SequenceAnnuelle
from apps.formations.models import Formation
from apps.referentiels.models import Institution

REGION_PAR_LIBELLE = {
    "Djibouti": "djibouti",
    "Ali Sabieh": "ali_sabieh",
    "Arta": "arta",
    "Dikhil": "dikhil",
    "Tadjourah": "tadjourah",
    "Obock": "obock",
}

DOMAINES = ["Informatique", "Gestion & administration", "Entrepreneuriat", "Technique", "Langues"]

# Ordre = ordre des identifiants (B-2026-0001 en premier) : la génération
# séquentielle du modèle (Beneficiaire.save) reproduit alors exactement les
# identifiants attendus par le formulaire Kobo.
BENEFICIAIRES_TERRAIN = [
    ("Ahmed", "Ismaïl", "M", "EFTP", "Djibouti", "77111137", "2026-06-26"),
    ("Fatouma", "Abdi", "F", "EFTP", "Djibouti", "77121274", "2026-06-26"),
    ("Moussa", "Hassan", "M", "ANEFIP", "Ali Sabieh", "77131411", "2026-06-26"),
    ("Hodan", "Omar", "F", "INAP", "Djibouti", "77141548", "2026-06-26"),
    ("Idriss", "Robleh", "M", "EFTP", "Arta", "77151685", "2026-06-26"),
    ("Sahra", "Youssouf", "F", "ANEFIP", "Dikhil", "77161822", "2026-06-26"),
    ("Kadar", "Waberi", "M", "INAP", "Djibouti", "77171959", "2026-06-26"),
    ("Amina", "Farah", "F", "EFTP", "Tadjourah", "77182096", "2026-06-26"),
    ("Osman", "Guedi", "M", "ANEFIP", "Obock", "77192233", "2026-04-17"),
    ("Nima", "Ali", "F", "INAP", "Djibouti", "77202370", "2026-06-26"),
    ("Abdourahman", "Djama", "M", "EFTP", "Ali Sabieh", "77212507", "2026-06-26"),
    ("Ifrah", "Bourhan", "F", "ANEFIP", "Arta", "77222644", "2026-06-26"),
    ("Souleiman", "Ahmed", "M", "EFTP", "Djibouti", "77232781", "2026-11-27"),
    ("Hawa", "Miguil", "F", "INAP", "Dikhil", "77242918", "2026-11-27"),
    ("Yacin", "Abdallah", "M", "ANEFIP", "Djibouti", "77253055", "2026-11-27"),
    ("Zeinab", "Hared", "F", "EFTP", "Tadjourah", "77263192", "2026-11-27"),
    ("Mahdi", "Elmi", "M", "INAP", "Obock", "77273329", "2026-09-18"),
    ("Roda", "Aden", "F", "EFTP", "Djibouti", "77283466", "2026-11-27"),
    ("Bilan", "Houssein", "F", "ANEFIP", "Ali Sabieh", "77293603", "2026-11-27"),
    ("Ali", "Wais", "M", "INAP", "Arta", "77303740", "2026-09-18"),
]


class Command(BaseCommand):
    help = "Remplace les bénéficiaires de démonstration par ceux du formulaire Kobo réellement déployé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmer", action="store_true",
            help="Confirme la suppression des bénéficiaires existants et de leurs données liées.",
        )

    def handle(self, *args, **options):
        if not options["confirmer"]:
            self.stderr.write(self.style.WARNING(
                "Cette commande supprime TOUS les bénéficiaires existants (et leurs formations/"
                "certifications/insertions/suivis/satisfactions). Relancer avec --confirmer pour exécuter."
            ))
            return

        nb_supprimes, _ = Beneficiaire.objects.all().delete()
        SequenceAnnuelle.objects.all().delete()
        self.stdout.write(f"{nb_supprimes} enregistrement(s) supprimé(s) (bénéficiaires et données liées).")

        institutions = {i.libelle: i for i in Institution.objects.all()}
        for index, (prenom, nom, sexe, institution_libelle, region_libelle, telephone, date_fin_str) in enumerate(
            BENEFICIAIRES_TERRAIN
        ):
            date_fin = date.fromisoformat(date_fin_str)
            # max(...) : certaines dates de fin de formation sont assez tot dans l'annee
            # pour que "- 150 jours" retombe en 2025, ce qui decalerait le prefixe de
            # l'identifiant genere (B-2025-... au lieu de B-2026-...) et desalignerait
            # toute la sequence par rapport aux identifiants attendus par le formulaire.
            date_debut = max(date_fin - timedelta(days=150), date(2026, 1, 15))
            beneficiaire = Beneficiaire.objects.create(
                nom=nom, prenom=prenom, sexe=sexe,
                date_naissance=date(1996 + (index % 12), 1 + (index % 12), 5 + (index % 20)),
                region=REGION_PAR_LIBELLE[region_libelle],
                institution=institutions[institution_libelle],
                telephone=telephone,
                date_enregistrement=date_debut,
            )
            Formation.objects.create(
                beneficiaire=beneficiaire, domaine=DOMAINES[index % len(DOMAINES)],
                date_debut=date_debut, date_fin=date_fin, statut_formation="achevee",
            )
            self.stdout.write(f"{beneficiaire.id_beneficiaire} — {prenom} {nom} ({institution_libelle})")

        self.stdout.write(self.style.SUCCESS(f"{len(BENEFICIAIRES_TERRAIN)} bénéficiaire(s) créé(s)."))
