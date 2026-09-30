import csv
from datetime import date
from io import StringIO
from pathlib import Path
from unittest import mock

import openpyxl
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.formations.models import Formation
from apps.referentiels.models import CycleEnquete, Institution

from .models import KoboSoumission
from .services import traiter_soumission

FICHIERS_KOBO = ["suivi_et_satisfaction.xlsx", "satisfaction_institution.xlsx"]


class ExportKoboChoicesTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        CycleEnquete.objects.create(libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30))
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.institution, telephone="77000000",
        )
        Formation.objects.create(
            beneficiaire=self.beneficiaire, domaine="Informatique",
            date_debut=date(2026, 1, 1), date_fin=date(2026, 6, 30),
        )

    def test_ecrit_les_csv_avec_le_bon_format(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=Path(tmp)):
                call_command("export_kobo_choices", stdout=StringIO())
                dossier = Path(tmp) / "kobo_forms" / "media"
                for nom in ("beneficiaires.csv", "institutions.csv"):
                    self.assertTrue((dossier / nom).exists(), f"{nom} devrait exister")

                with open(dossier / "beneficiaires.csv", encoding="utf-8") as f:
                    lignes = list(csv.DictReader(f))
                self.assertEqual(lignes[0]["name"], "B-2026-0001")
                self.assertIn("Ali", lignes[0]["label"])
                self.assertEqual(lignes[0]["nom_prenom"], "Amina Ali")
                self.assertEqual(lignes[0]["institution"], "DGFP")
                self.assertEqual(lignes[0]["date_fin_formation"], "2026-06-30")
                self.assertEqual(lignes[0]["telephone"], "77000000")

                with open(dossier / "institutions.csv", encoding="utf-8") as f:
                    lignes = list(csv.DictReader(f))
                self.assertEqual(lignes[0]["name"], str(self.institution.pk))
                self.assertEqual(lignes[0]["label"], "DGFP")


class GenerateKoboXlsformsTests(TestCase):
    def test_genere_les_formulaires_valides(self):
        import tempfile
        from openpyxl import load_workbook

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=Path(tmp)):
                call_command("generate_kobo_xlsforms", stdout=StringIO())
                dossier = Path(tmp) / "kobo_forms"
                for nom in FICHIERS_KOBO:
                    chemin = dossier / nom
                    self.assertTrue(chemin.exists(), f"{nom} devrait exister")
                    classeur = load_workbook(chemin)
                    self.assertEqual(set(classeur.sheetnames), {"survey", "choices", "settings"})
                    noms_champs = [row[1].value for row in classeur["survey"].iter_rows(min_row=2) if row[1].value]
                    self.assertIn("id_beneficiaire" if "institution" not in nom else "institution", noms_champs)

    def test_pyxform_accepte_les_formulaires_generes(self):
        """Le meme moteur de validation que celui utilise par KoboToolbox a l'import."""
        import tempfile

        from pyxform.xls2xform import xls2xform_convert

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=Path(tmp)):
                call_command("generate_kobo_xlsforms", stdout=StringIO())
                dossier = Path(tmp) / "kobo_forms"
                for nom in FICHIERS_KOBO:
                    resultat = xls2xform_convert(str(dossier / nom), str(dossier / (nom + ".xml")), validate=False)
                    self.assertEqual(resultat, [], f"{nom} : avertissements pyxform inattendus")


class TraiterSoumissionTests(TestCase):
    """La logique d'intégration/retraitement partagée par la synchro automatique
    et le bouton « Réessayer » de la page de contrôle."""

    def setUp(self):
        institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution,
        )

    def test_reessai_reussi_efface_le_message_d_erreur_precedent(self):
        soumission = KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="1", statut="erreur",
            erreur="Bénéficiaire introuvable : B-0000",
            donnees_brutes={
                "selection/id_beneficiaire": self.beneficiaire.pk,
                "selection/date_contact": "2026-01-01",
                "issue_contact": "injoignable",
                "module_suivi/vague": "m3",
            },
        )
        reussite = traiter_soumission(soumission)
        soumission.refresh_from_db()
        self.assertTrue(reussite)
        self.assertEqual(soumission.statut, "integre")
        self.assertEqual(soumission.erreur, "")

    def test_echec_enregistre_le_message_d_erreur(self):
        soumission = KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="2", statut="nouveau",
            donnees_brutes={
                "selection/id_beneficiaire": "B-INCONNU", "module_suivi/vague": "m3",
                "issue_contact": "injoignable",
            },
        )
        reussite = traiter_soumission(soumission)
        soumission.refresh_from_db()
        self.assertFalse(reussite)
        self.assertEqual(soumission.statut, "erreur")
        self.assertIn("B-INCONNU", soumission.erreur)

    def test_soumission_avec_module_satisfaction_cree_aussi_une_satisfaction(self):
        from apps.satisfactions.models import Satisfaction

        CycleEnquete.objects.create(libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30))
        soumission = KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="3", statut="nouveau",
            donnees_brutes={
                "selection/id_beneficiaire": self.beneficiaire.pk,
                "selection/date_contact": "2026-12-01",
                "issue_contact": "joint",
                "module_suivi/vague": "m3",
                "module_suivi/situation": "inactif",
                "bascule/faire_satisfaction": "oui",
                "bascule/cycle": "cycle_1",
                "bascule/note_formation": 4, "bascule/note_formateurs": 5, "bascule/note_contenus": 4,
                "bascule/note_equipements": 4, "bascule/note_conditions": 5,
                "bascule/employabilite": "tout_a_fait", "bascule/recommande": "oui",
            },
        )
        reussite = traiter_soumission(soumission)
        self.assertTrue(reussite)
        satisfaction = Satisfaction.objects.get(beneficiaire=self.beneficiaire)
        self.assertEqual(satisfaction.note_accueil, 5)
        self.assertTrue(satisfaction.recommande)


class SoumissionListViewTests(TestCase):
    def setUp(self):
        self.validateur = User.objects.create_user(username="validateur_test", password="motdepasse123")
        Profile.objects.filter(user=self.validateur).update(role="validateur")
        self.consultation = User.objects.create_user(username="consultation_test", password="motdepasse123")
        Profile.objects.filter(user=self.consultation).update(role="consultation")
        KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="1", statut="erreur",
            erreur="Bénéficiaire introuvable", donnees_brutes={},
        )
        KoboSoumission.objects.create(type_formulaire="suivi", kobo_submission_id="2", statut="integre", donnees_brutes={})

    def test_role_consultation_refuse(self):
        self.client.force_login(self.consultation)
        response = self.client.get(reverse("imports:liste"))
        self.assertEqual(response.status_code, 403)

    def test_role_validateur_voit_la_liste_et_les_compteurs(self):
        self.client.force_login(self.validateur)
        response = self.client.get(reverse("imports:liste"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nb_total"], 2)
        self.assertEqual(response.context["nb_erreur"], 1)
        self.assertEqual(response.context["nb_integre"], 1)

    def test_filtre_par_statut(self):
        self.client.force_login(self.validateur)
        response = self.client.get(reverse("imports:liste"), {"statut": "erreur"})
        soumissions = list(response.context["soumissions"])
        self.assertEqual(len(soumissions), 1)
        self.assertEqual(soumissions[0].kobo_submission_id, "1")


class SoumissionActionsViewTests(TestCase):
    def setUp(self):
        self.validateur = User.objects.create_user(username="validateur_test2", password="motdepasse123")
        Profile.objects.filter(user=self.validateur).update(role="validateur")
        institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution,
        )

    def test_reessayer_integre_une_soumission_desormais_valide(self):
        soumission = KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="1", statut="erreur", erreur="Bénéficiaire introuvable",
            donnees_brutes={
                "selection/id_beneficiaire": self.beneficiaire.pk,
                "selection/date_contact": "2026-01-01",
                "issue_contact": "injoignable",
                "module_suivi/vague": "m3",
            },
        )
        self.client.force_login(self.validateur)
        response = self.client.post(reverse("imports:reessayer", args=[soumission.pk]))
        self.assertRedirects(response, reverse("imports:detail", args=[soumission.pk]))
        soumission.refresh_from_db()
        self.assertEqual(soumission.statut, "integre")

    def test_marquer_doublon_ecarte_la_soumission(self):
        soumission = KoboSoumission.objects.create(
            type_formulaire="suivi", kobo_submission_id="1", statut="erreur", donnees_brutes={},
        )
        self.client.force_login(self.validateur)
        response = self.client.post(reverse("imports:marquer_doublon", args=[soumission.pk]))
        self.assertRedirects(response, reverse("imports:liste"))
        soumission.refresh_from_db()
        self.assertEqual(soumission.statut, "doublon")


def _classeur_liste_nominative(tmp_path, lignes_beneficiaires, lignes_formations):
    """Construit un fichier au format "PDCED-Skills_<INSTITUTION>-liste-nominative.xlsx"
    (mêmes colonnes, mêmes dates en texte que les vraies listes institutionnelles)."""
    classeur = openpyxl.Workbook()
    feuille_b = classeur.active
    feuille_b.title = "beneficiaires"
    feuille_b.append([
        "id_beneficiaire", "nom_complet", "sexe", "date_naissance", "age_declare",
        "quartier", "region", "niveau_etude", "telephone_1", "id_institution", "statut",
    ])
    for ligne in lignes_beneficiaires:
        feuille_b.append(ligne)
    feuille_f = classeur.create_sheet("formations")
    feuille_f.append(["id_formation", "id_beneficiaire", "filiere", "centre", "date_debut", "date_fin"])
    for ligne in lignes_formations:
        feuille_f.append(ligne)
    chemin = tmp_path / "liste.xlsx"
    classeur.save(chemin)
    return str(chemin)


class ImportBeneficiairesExcelTests(TestCase):
    """Cette commande a causé un incident réel : l'import de la liste DGFP a réassigné
    un bénéficiaire ANEFIP à cause d'un homonyme (même nom, même date de naissance,
    aucune date de naissance dans d'autres cas). Ces tests couvrent précisément ce qui
    a été corrigé pour que ça ne se reproduise pas."""

    def setUp(self):
        self.anefip = Institution.objects.create(libelle="ANEFIP", type="anefip", region="djibouti")
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")

    def test_import_cree_les_beneficiaires_et_formations(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fichier = _classeur_liste_nominative(
                Path(tmp),
                [("X-0001", "AMINA ALI ROBLEH", "F", "1999-03-01", 27, "Balbala", "Djibouti", "BAC", 77000000, "ANEFIP", "formé")],
                [("F-0001", "X-0001", "Informatique", "Centre A", "2026-01-10", "2026-06-10")],
            )
            call_command("import_beneficiaires_excel", fichier, stdout=StringIO())
        b = Beneficiaire.objects.get(institution=self.anefip)
        self.assertEqual((b.nom, b.prenom), ("ALI ROBLEH", "AMINA"))
        self.assertEqual(b.sexe, "F")
        formation = Formation.objects.get(beneficiaire=b)
        self.assertEqual(formation.statut_formation, "achevee")

    def test_champs_manquants_ne_font_pas_planter_limport(self):
        # Régression : une liste nominative réelle contenait des formations sans filière
        # (colonne "filiere" vide, un centre donné) - Formation.domaine ne peut alors plus
        # être obligatoire, sous peine de faire planter tout l'import en cours de route.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fichier = _classeur_liste_nominative(
                Path(tmp),
                [("X-0001", "IDRISS ROBLEH", None, None, None, None, "Djibouti", None, None, "DGFP", "en cours")],
                [("F-0001", "X-0001", None, "Centre B", None, None)],
            )
            call_command("import_beneficiaires_excel", fichier, stdout=StringIO())
        b = Beneficiaire.objects.get(institution=self.dgfp)
        self.assertEqual(b.sexe, "")
        self.assertIsNone(b.date_naissance)
        formation = Formation.objects.get(beneficiaire=b)
        self.assertIsNone(formation.date_debut)
        self.assertEqual(formation.domaine, "")

    def test_un_homonyme_dans_une_autre_institution_nest_pas_confondu(self):
        # Régression exacte de l'incident : un bénéficiaire ANEFIP existant ne doit
        # jamais être réassigné à une autre institution à cause d'un homonyme (même nom,
        # même date de naissance) rencontré dans le fichier importé.
        Beneficiaire.objects.create(
            nom="Ahmed", prenom="Mohamed", sexe="M", date_naissance=date(1996, 11, 17),
            region="djibouti", institution=self.anefip,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fichier = _classeur_liste_nominative(
                Path(tmp),
                [("X-0001", "MOHAMED AHMED", "M", "1996-11-17", 30, None, "Djibouti", None, 77000001, "DGFP", "formé")],
                [],
            )
            call_command("import_beneficiaires_excel", fichier, stdout=StringIO())
        self.assertEqual(Beneficiaire.objects.filter(institution=self.anefip).count(), 1)
        self.assertEqual(Beneficiaire.objects.filter(institution=self.dgfp).count(), 1)

    def test_reprise_transparente_apres_une_coupure_reseau(self):
        # Le pooler Supabase coupe parfois une connexion en plein import (flake réseau
        # constaté en conditions réelles) : une seule ligne doit être rejouée, pas tout
        # l'import - et surtout pas en le relançant depuis le début (cf. l'autre incident :
        # ça duplique les bénéficiaires sans date de naissance connue).
        appels = {"n": 0}
        original_save = Beneficiaire.save

        def save_qui_echoue_une_fois(self, *args, **kwargs):
            appels["n"] += 1
            if appels["n"] == 1:
                raise OperationalError("server closed the connection unexpectedly")
            return original_save(self, *args, **kwargs)

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fichier = _classeur_liste_nominative(
                Path(tmp),
                [("X-0001", "AMINA ALI", "F", "1999-03-01", 27, None, "Djibouti", None, 77000000, "ANEFIP", "formé")],
                [],
            )
            with mock.patch("apps.beneficiaires.models.Beneficiaire.save", save_qui_echoue_une_fois), \
                 mock.patch("apps.imports.management.commands.import_beneficiaires_excel.time.sleep"), \
                 mock.patch("apps.imports.management.commands.import_beneficiaires_excel.connection.close"):
                # connection.close() n'est pas exercé pour de vrai : les TestCase de Django
                # isolent chaque test dans une transaction non validée, et fermer la vraie
                # connexion casserait ce mécanisme pour les tests suivants - seule la
                # logique de reprise (rejouer la ligne) nous intéresse ici.
                call_command("import_beneficiaires_excel", fichier, stdout=StringIO())
        self.assertEqual(Beneficiaire.objects.filter(institution=self.anefip).count(), 1)
        self.assertEqual(appels["n"], 2)
