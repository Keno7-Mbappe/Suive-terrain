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
        self.eftp = Institution.objects.create(libelle="EFTP", type="eftp", region="djibouti")
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
            "note_formation": 4, "note_formateurs": 4, "note_contenus": 4,
            "note_equipements": 4, "note_accueil": 4,
        })
        self.assertEqual(response.status_code, 302)
        reponse = SatisfactionInstitution.objects.get(cycle=self.cycle)
        self.assertEqual(reponse.institution_id, self.eftp.pk)

    def test_liste_institution_accessible(self):
        self.client.force_login(self.saisie)
        response = self.client.get(reverse("satisfactions:liste_institution"))
        self.assertEqual(response.status_code, 200)
