from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import Institution

from .models import Formation


class FormationScopingTests(TestCase):
    def setUp(self):
        self.eftp = Institution.objects.create(libelle="EFTP", type="eftp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.beneficiaire_eftp = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.eftp,
        )
        self.beneficiaire_inap = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="djibouti", institution=self.inap,
        )
        self.saisie_eftp = User.objects.create_user(username="saisie_eftp", password="motdepasse123")
        Profile.objects.filter(user=self.saisie_eftp).update(role="saisie", institution=self.eftp)

    def test_formulaire_de_creation_ne_propose_que_les_beneficiaires_de_linstitution(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.get(reverse("formations:creer"))
        choix = list(response.context["form"].fields["beneficiaire"].queryset)
        self.assertIn(self.beneficiaire_eftp, choix)
        self.assertNotIn(self.beneficiaire_inap, choix)

    def test_creation_et_liste_scopee(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.post(reverse("formations:creer"), {
            "beneficiaire": self.beneficiaire_eftp.pk, "domaine": "Informatique",
            "date_debut": "2026-01-10", "statut_formation": "en_cours",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Formation.objects.filter(beneficiaire=self.beneficiaire_eftp).count(), 1)

        liste = self.client.get(reverse("formations:liste"))
        self.assertEqual(len(liste.context["formations"]), 1)
