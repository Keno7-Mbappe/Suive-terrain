"""Circuit de validation des soumissions Kobo : rien de ce qui vient de Kobo
n'entre dans la base sans relecture humaine (lecture en clair, correction,
suppression, puis validation) - et la liste des bénéficiaires du formulaire
Kobo reste alignée sur la base."""

import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.formations.models import Formation
from apps.referentiels.models import CycleEnquete, Institution
from apps.satisfactions.models import SatisfactionInstitution
from apps.suivis.models import Suivi

from .models import KoboSoumission
from .services import traiter_soumission


def donnees_suivi(beneficiaire, **surcharges):
    donnees = {
        "selection/id_beneficiaire": beneficiaire.pk,
        "selection/nom_prenom": f"{beneficiaire.prenom} {beneficiaire.nom}",
        "selection/canal": "visite",
        "selection/date_contact": "2026-09-03",
        "issue_contact": "joint",
        "module_suivi/vague": "m3",
        "module_suivi/situation": "stage",
        "module_suivi/secteur": "administration",
        "module_suivi/date_debut_activite": "2026-07-01",
        "module_suivi/lien_formation": "direct",
    }
    donnees.update(surcharges)
    return donnees


class FluxDeValidationTests(TestCase):
    def setUp(self):
        self.eftp = Institution.objects.create(libelle="EFTP", type="eftp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali Ahmed", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.eftp,
        )
        self.validateur = User.objects.create_user(username="valid_global", password="motdepasse123")
        Profile.objects.filter(user=self.validateur).update(role="validateur")
        self.validateur_inap = User.objects.create_user(username="valid_inap", password="motdepasse123")
        Profile.objects.filter(user=self.validateur_inap).update(role="validateur", institution=self.inap)

    def _soumission(self, donnees=None, **champs):
        return KoboSoumission.objects.create(
            type_formulaire=champs.pop("type_formulaire", "suivi"),
            kobo_submission_id=champs.pop("kobo_submission_id", "1"),
            donnees_brutes=donnees if donnees is not None else donnees_suivi(self.beneficiaire),
            institution=champs.pop("institution", self.eftp),
            **champs,
        )

    # --- synchronisation : tout arrive "à valider" ---------------------------------

    @override_settings(KOBO_ASSET_UID_SUIVI="aTEST", KOBO_ASSET_UID_SATISFACTION_INSTITUTION="")
    def test_la_synchro_depose_les_soumissions_a_valider_sans_les_integrer(self):
        recues = [{"_id": 501, **donnees_suivi(self.beneficiaire)}]
        with mock.patch("apps.imports.services.fetch_kobo_submissions", return_value=recues):
            call_command("sync_kobo", stdout=StringIO())
        soumission = KoboSoumission.objects.get(kobo_submission_id="501")
        self.assertEqual(soumission.statut, "nouveau")
        self.assertEqual(soumission.institution, self.eftp)
        self.assertEqual(Suivi.objects.count(), 0)

    @override_settings(KOBO_ASSET_UID_SUIVI="aTEST", KOBO_ASSET_UID_SATISFACTION_INSTITUTION="")
    def test_option_integrer_conserve_l_ancien_comportement_automatique(self):
        recues = [{"_id": 502, **donnees_suivi(self.beneficiaire)}]
        with mock.patch("apps.imports.services.fetch_kobo_submissions", return_value=recues):
            call_command("sync_kobo", "--integrer", stdout=StringIO())
        self.assertEqual(KoboSoumission.objects.get(kobo_submission_id="502").statut, "integre")
        self.assertEqual(Suivi.objects.count(), 1)

    # --- actualisation depuis Kobo -------------------------------------------------

    @override_settings(KOBO_ASSET_UID_SUIVI="aTEST", KOBO_ASSET_UID_SATISFACTION_INSTITUTION="")
    def test_le_bouton_actualiser_depose_les_nouvelles_soumissions_a_valider(self):
        recues = [{"_id": 601, **donnees_suivi(self.beneficiaire)}]
        self.client.force_login(self.validateur)
        with mock.patch("apps.imports.services.fetch_kobo_submissions", return_value=recues):
            response = self.client.post(reverse("imports:actualiser"))
        self.assertRedirects(response, reverse("imports:liste"))
        self.assertEqual(KoboSoumission.objects.get(kobo_submission_id="601").statut, "nouveau")
        self.assertEqual(Suivi.objects.count(), 0)
        self.assertTrue(any("1 nouvelle" in str(m) for m in get_messages(response.wsgi_request)))

    def test_un_formulaire_kobo_indisponible_n_empeche_pas_les_autres(self):
        def sync_factice(type_formulaire):
            if type_formulaire == "satisfaction_institution":
                raise requests.HTTPError(response=mock.Mock(status_code=404))
            return {"recues": 2, "nouvelles": 2}

        self.client.force_login(self.validateur)
        with mock.patch("apps.imports.services.sync_form", side_effect=sync_factice):
            response = self.client.post(reverse("imports:actualiser"))
        textes = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("2 nouvelle" in t for t in textes))
        self.assertTrue(any("non déployé" in t for t in textes))

    def test_seul_un_validateur_peut_actualiser(self):
        simple = User.objects.create_user(username="saisie_y", password="motdepasse123")
        Profile.objects.filter(user=simple).update(role="saisie")
        self.client.force_login(simple)
        self.assertEqual(self.client.post(reverse("imports:actualiser")).status_code, 403)

    # --- lecture -------------------------------------------------------------------

    def test_la_fiche_affiche_le_formulaire_en_clair(self):
        soumission = self._soumission()
        self.client.force_login(self.validateur)
        response = self.client.get(reverse("imports:detail", args=[soumission.pk]))
        self.assertEqual(response.status_code, 200)
        for attendu in ("Canal du contact", "Visite", "Stage", "Administration publique", "Amina Ali Ahmed"):
            self.assertContains(response, attendu)

    def test_la_fiche_signale_un_nom_different_de_celui_de_la_base(self):
        donnees = donnees_suivi(self.beneficiaire, **{"selection/nom_prenom": "Quelqu'un d'autre"})
        soumission = self._soumission(donnees)
        self.client.force_login(self.validateur)
        response = self.client.get(reverse("imports:detail", args=[soumission.pk]))
        messages = [m for niveau, m in response.context["alertes"] if niveau == "attention"]
        self.assertTrue(any("désynchronisée" in m for m in messages))

    def test_un_validateur_ne_voit_que_les_soumissions_de_son_institution(self):
        soumission = self._soumission()
        self.client.force_login(self.validateur_inap)
        self.assertEqual(self.client.get(reverse("imports:detail", args=[soumission.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("imports:liste")).context["nb_total"], 0)

    # --- correction ----------------------------------------------------------------

    def _post_correction(self, soumission, **surcharges):
        donnees = {
            "selection__id_beneficiaire": self.beneficiaire.pk,
            "selection__canal": "telephone",
            "selection__date_contact": "2026-09-03",
            "issue_contact": "joint",
            "module_suivi__vague": "m6",
            "module_suivi__situation": "stage",
            "module_suivi__secteur": "banque",
        }
        donnees.update(surcharges)
        return self.client.post(reverse("imports:corriger", args=[soumission.pk]), donnees)

    def test_la_correction_ne_touche_pas_aux_donnees_brutes_et_c_est_elle_qui_est_integree(self):
        soumission = self._soumission()
        self.client.force_login(self.validateur)
        response = self._post_correction(soumission)
        self.assertRedirects(response, reverse("imports:detail", args=[soumission.pk]))
        soumission.refresh_from_db()
        self.assertEqual(soumission.donnees_brutes["module_suivi/vague"], "m3")
        self.assertEqual(soumission.donnees_corrigees["module_suivi/vague"], "m6")
        self.assertNotIn("module_suivi/lien_formation", soumission.donnees_corrigees)  # champ vidé
        self.assertEqual(soumission.statut, "nouveau")

        self.client.post(reverse("imports:valider", args=[soumission.pk]))
        suivi = Suivi.objects.get(beneficiaire=self.beneficiaire)
        self.assertEqual(suivi.vague, "m6")
        self.assertEqual(suivi.secteur_activite, "banque")
        self.assertEqual(suivi.canal, "telephone")
        soumission.refresh_from_db()
        self.assertEqual(soumission.traite_par, self.validateur)

    def test_la_correction_refuse_un_beneficiaire_inconnu(self):
        soumission = self._soumission()
        self.client.force_login(self.validateur)
        response = self._post_correction(soumission, selection__id_beneficiaire="B-INCONNU")
        self.assertEqual(response.status_code, 200)
        self.assertIn("selection__id_beneficiaire", response.context["form"].errors)
        soumission.refresh_from_db()
        self.assertIsNone(soumission.donnees_corrigees)

    def test_corriger_une_soumission_integree_la_remet_a_valider(self):
        soumission = self._soumission(statut="integre")
        self.client.force_login(self.validateur)
        self._post_correction(soumission)
        soumission.refresh_from_db()
        self.assertEqual(soumission.statut, "nouveau")

    # --- validation ----------------------------------------------------------------

    def test_vague_manquante_bloque_la_validation_avec_un_message_clair(self):
        donnees = donnees_suivi(self.beneficiaire, issue_contact="injoignable")
        del donnees["module_suivi/vague"]
        soumission = self._soumission(donnees)
        self.client.force_login(self.validateur)
        self.client.post(reverse("imports:valider", args=[soumission.pk]))
        soumission.refresh_from_db()
        self.assertEqual(soumission.statut, "erreur")
        self.assertIn("Vague de suivi manquante", soumission.erreur)
        self.assertEqual(Suivi.objects.count(), 0)

        # Le formulaire de correction propose la vague la plus proche des mois écoulés.
        soumission.donnees_brutes["selection/mois_ecoules"] = "5"
        soumission.save()
        response = self.client.get(reverse("imports:corriger", args=[soumission.pk]))
        self.assertEqual(response.context["form"].initial["module_suivi__vague"], "m6")

    def test_satisfaction_institution_reconnait_le_code_de_l_institution_kobo(self):
        CycleEnquete.objects.create(libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30))
        soumission = self._soumission(
            {
                "identification/institution": "EFTP", "identification/cycle": "cycle_1",
                "identification/fonction": "Directeur",
                "notes/note_qualite_donnees": "4", "notes/note_outils_collecte": "4",
                "notes/note_tableaux_bord": "5", "notes/note_appui_technique": "3",
                "notes/note_coordination": "4", "utilite_dispositif": "pleinement",
            },
            type_formulaire="satisfaction_institution",
        )
        self.assertTrue(traiter_soumission(soumission))
        reponse = SatisfactionInstitution.objects.get(institution=self.eftp)
        self.assertEqual(reponse.fonction_repondant, "Directeur")
        self.assertEqual(reponse.note_globale, 4.0)

    # --- suppression ---------------------------------------------------------------

    def test_supprimer_une_soumission_a_valider(self):
        soumission = self._soumission()
        self.client.force_login(self.validateur)
        response = self.client.post(reverse("imports:supprimer", args=[soumission.pk]))
        self.assertRedirects(response, reverse("imports:liste"))
        self.assertFalse(KoboSoumission.objects.filter(pk=soumission.pk).exists())

    def test_une_soumission_integree_ne_peut_pas_etre_supprimee(self):
        soumission = self._soumission(statut="integre")
        self.client.force_login(self.validateur)
        self.client.post(reverse("imports:supprimer", args=[soumission.pk]))
        self.assertTrue(KoboSoumission.objects.filter(pk=soumission.pk).exists())

    def test_seul_un_validateur_peut_agir(self):
        soumission = self._soumission()
        simple = User.objects.create_user(username="saisie_x", password="motdepasse123")
        Profile.objects.filter(user=simple).update(role="saisie")
        self.client.force_login(simple)
        for nom in ("detail", "corriger"):
            self.assertEqual(self.client.get(reverse(f"imports:{nom}", args=[soumission.pk])).status_code, 403)
        for nom in ("valider", "supprimer", "marquer_doublon"):
            self.assertEqual(self.client.post(reverse(f"imports:{nom}", args=[soumission.pk])).status_code, 403)
        self.assertTrue(KoboSoumission.objects.filter(pk=soumission.pk, statut="nouveau").exists())

    # --- tableau de bord -----------------------------------------------------------

    def test_le_tableau_de_bord_signale_les_soumissions_a_traiter_aux_validateurs_seulement(self):
        self._soumission()
        self.client.force_login(self.validateur)
        interne = self.client.get(reverse("dashboard:index"))
        self.assertEqual(interne.context["nb_soumissions_a_valider"], 1)
        self.assertContains(interne, "soumission(s) Kobo à traiter")
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("dashboard:public")), "soumission(s) Kobo à traiter")


class PublierBeneficiairesKoboTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(libelle="ANEFIP", type="anefip", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="ABDILLAHI GUELLEH", prenom="ABAS", sexe="M", date_naissance=date(1999, 5, 3),
            region="djibouti", institution=self.institution, telephone="77427720",
        )
        Formation.objects.create(
            beneficiaire=self.beneficiaire, domaine="AGENT DE SECURITE",
            date_debut=date(2025, 9, 10), date_fin=date(2025, 9, 17),
        )

    def test_remplace_uniquement_la_liste_des_beneficiaires_et_redeploie(self):
        asset = {
            "uid": "aTEST",
            "content": {"choices": [
                {"list_name": "cycle", "name": "cycle_1", "label": ["Cycle 1"]},
                {"list_name": "beneficiaire", "name": "B-2026-0001", "label": ["ancien"]},
            ]},
        }
        with tempfile.TemporaryDirectory() as tmp, override_settings(
            BASE_DIR=Path(tmp), KOBO_API_TOKEN="jeton", KOBO_ASSET_UID_SUIVI="aTEST"
        ), mock.patch("apps.imports.management.commands.publier_beneficiaires_kobo.requests") as requests:
            requests.get.return_value.json.return_value = asset
            requests.patch.return_value.ok = True
            requests.patch.return_value.json.return_value = {"version_id": "v2"}
            call_command("publier_beneficiaires_kobo", stdout=StringIO())

            envoye = requests.patch.call_args_list[0].kwargs["json"]["content"]["choices"]
            self.assertIn({"list_name": "cycle", "name": "cycle_1", "label": ["Cycle 1"]}, envoye)
            beneficiaires = [c for c in envoye if c["list_name"] == "beneficiaire"]
            self.assertEqual(len(beneficiaires), 1)
            self.assertEqual(beneficiaires[0]["name"], "B-2026-0001")
            self.assertEqual(beneficiaires[0]["nom_prenom"], "ABAS ABDILLAHI GUELLEH")
            self.assertEqual(beneficiaires[0]["date_fin_formation"], "2025-09-17")
            self.assertEqual(beneficiaires[0]["institution"], "ANEFIP")
            self.assertNotIn("ancien", str(beneficiaires))

            redeploiement = requests.patch.call_args_list[1]
            self.assertTrue(redeploiement.args[0].endswith("/aTEST/deployment/"))
            self.assertEqual(redeploiement.kwargs["json"]["version_id"], "v2")
            self.assertEqual(len(list((Path(tmp) / "kobo_forms" / "sauvegardes").glob("aTEST_*.json"))), 1)

    def test_dry_run_ne_modifie_rien(self):
        with override_settings(KOBO_API_TOKEN="jeton", KOBO_ASSET_UID_SUIVI="aTEST"), mock.patch(
            "apps.imports.management.commands.publier_beneficiaires_kobo.requests"
        ) as requests:
            requests.get.return_value.json.return_value = {"uid": "aTEST", "content": {"choices": []}}
            call_command("publier_beneficiaires_kobo", "--dry-run", stdout=StringIO())
            requests.patch.assert_not_called()
