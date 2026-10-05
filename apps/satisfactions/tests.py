from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import CycleEnquete, Institution

from .models import Satisfaction, SatisfactionInstitution


class SatisfactionViewsTests(TestCase):
    def setUp(self):
        self.eftp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.cycle = CycleEnquete.objects.create(
            libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30)
        )
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.eftp,
        )
        self.saisie = User.objects.create_user(username="saisie_eftp", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie", institution=self.eftp)

    def test_creer_satisfaction_beneficiaire(self):
        self.client.force_login(self.saisie)
        response = self.client.post(reverse("satisfactions:creer"), {
            "beneficiaire": self.beneficiaire.pk, "cycle": self.cycle.pk,
            "note_formation": 4, "note_formateurs": 5, "note_contenus": 4,
            "note_equipements": 3, "note_accueil": 4,
            "amelioration_employabilite": "tout_a_fait", "recommande": "on",
        })
        self.assertEqual(response.status_code, 302)
        satisfaction = Satisfaction.objects.get(beneficiaire=self.beneficiaire, cycle=self.cycle)
        self.assertEqual(satisfaction.note_globale, 4.0)

    def test_creer_satisfaction_institution_verrouille_institution(self):
        autre_institution = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.client.force_login(self.saisie)
        response = self.client.post(reverse("satisfactions:creer_institution"), {
            "institution": autre_institution.pk,  # tentative de forcer une autre institution
            "cycle": self.cycle.pk,
            "note_qualite_donnees": 4, "note_outils_collecte": 4, "note_tableaux_bord": 4,
            "note_appui_technique": 4, "note_coordination": 4, "utilite_dispositif": "pleinement",
        })
        self.assertEqual(response.status_code, 302)
        reponse = SatisfactionInstitution.objects.get(cycle=self.cycle)
        self.assertEqual(reponse.institution_id, self.eftp.pk)

    def test_liste_institution_accessible(self):
        self.client.force_login(self.saisie)
        response = self.client.get(reverse("satisfactions:liste_institution"))
        self.assertEqual(response.status_code, 200)


class SatisfactionSupprimerViewTests(TestCase):
    def setUp(self):
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.cycle = CycleEnquete.objects.create(
            libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30)
        )
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.dgfp,
        )
        self.satisfaction = Satisfaction.objects.create(
            beneficiaire=self.beneficiaire, cycle=self.cycle,
            note_formation=4, note_formateurs=4, note_contenus=4, note_equipements=4, note_accueil=4,
            amelioration_employabilite="tout_a_fait", recommande=True,
        )
        self.saisie = User.objects.create_user(username="saisie_test", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie", institution=self.dgfp)
        self.consultation = User.objects.create_user(username="consultation_test", password="motdepasse123")

    def test_supprime_la_satisfaction(self):
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("satisfactions:supprimer", args=[self.satisfaction.pk]))
        self.assertRedirects(reponse, reverse("satisfactions:liste"))
        self.assertFalse(Satisfaction.objects.filter(pk=self.satisfaction.pk).exists())

    def test_role_consultation_refuse(self):
        self.client.force_login(self.consultation)
        reponse = self.client.post(reverse("satisfactions:supprimer", args=[self.satisfaction.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(Satisfaction.objects.filter(pk=self.satisfaction.pk).exists())

    def test_ne_peut_pas_supprimer_une_satisfaction_dune_autre_institution(self):
        beneficiaire_inap = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="djibouti", institution=self.inap,
        )
        satisfaction_inap = Satisfaction.objects.create(
            beneficiaire=beneficiaire_inap, cycle=self.cycle,
            note_formation=4, note_formateurs=4, note_contenus=4, note_equipements=4, note_accueil=4,
            amelioration_employabilite="tout_a_fait", recommande=True,
        )
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("satisfactions:supprimer", args=[satisfaction_inap.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(Satisfaction.objects.filter(pk=satisfaction_inap.pk).exists())


class SatisfactionInstitutionSupprimerViewTests(TestCase):
    def setUp(self):
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.cycle = CycleEnquete.objects.create(
            libelle="Cycle 1", date_debut=date(2026, 11, 1), date_fin=date(2026, 11, 30)
        )
        self.satisfaction = SatisfactionInstitution.objects.create(
            institution=self.dgfp, cycle=self.cycle,
            note_qualite_donnees=4, note_outils_collecte=4, note_tableaux_bord=4,
            note_appui_technique=4, note_coordination=4, utilite_dispositif="pleinement",
        )
        self.saisie = User.objects.create_user(username="saisie_test2", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie", institution=self.dgfp)
        self.consultation = User.objects.create_user(username="consultation_test2", password="motdepasse123")

    def test_supprime_la_satisfaction_institution(self):
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("satisfactions:supprimer_institution", args=[self.satisfaction.pk]))
        self.assertRedirects(reponse, reverse("satisfactions:liste_institution"))
        self.assertFalse(SatisfactionInstitution.objects.filter(pk=self.satisfaction.pk).exists())

    def test_role_consultation_refuse(self):
        self.client.force_login(self.consultation)
        reponse = self.client.post(reverse("satisfactions:supprimer_institution", args=[self.satisfaction.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(SatisfactionInstitution.objects.filter(pk=self.satisfaction.pk).exists())

    def test_ne_peut_pas_supprimer_une_satisfaction_dune_autre_institution(self):
        satisfaction_inap = SatisfactionInstitution.objects.create(
            institution=self.inap, cycle=self.cycle,
            note_qualite_donnees=4, note_outils_collecte=4, note_tableaux_bord=4,
            note_appui_technique=4, note_coordination=4, utilite_dispositif="pleinement",
        )
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("satisfactions:supprimer_institution", args=[satisfaction_inap.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(SatisfactionInstitution.objects.filter(pk=satisfaction_inap.pk).exists())
