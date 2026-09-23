from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import Institution

from .models import Suivi


class SuiviScopingEtLogiqueTests(TestCase):
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
        response = self.client.get(reverse("suivis:creer"))
        choix = list(response.context["form"].fields["beneficiaire"].queryset)
        self.assertIn(self.beneficiaire_eftp, choix)
        self.assertNotIn(self.beneficiaire_inap, choix)

    def test_contact_joint_conserve_la_situation(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.post(reverse("suivis:creer"), {
            "beneficiaire": self.beneficiaire_eftp.pk, "vague": "m3", "date_suivi": "2026-04-01",
            "issue_contact": "joint", "situation_actuelle": "emploi_salarie",
            "type_contrat": "cdi", "secteur_activite": "Informatique",
            "tranche_revenu": "30000_60000", "lien_formation": "direct",
        })
        self.assertEqual(response.status_code, 302)
        suivi = Suivi.objects.get(beneficiaire=self.beneficiaire_eftp)
        self.assertEqual(suivi.situation_actuelle, "emploi_salarie")
        self.assertEqual(suivi.type_contrat, "cdi")

    def test_contact_injoignable_efface_la_situation_meme_si_soumise(self):
        # Un enquêteur pourrait laisser des valeurs résiduelles dans le formulaire ;
        # le formulaire doit les ignorer si le contact n'a pas abouti.
        self.client.force_login(self.saisie_eftp)
        response = self.client.post(reverse("suivis:creer"), {
            "beneficiaire": self.beneficiaire_eftp.pk, "vague": "m3", "date_suivi": "2026-04-01",
            "issue_contact": "injoignable", "situation_actuelle": "emploi_salarie",
            "type_contrat": "cdi",
        })
        self.assertEqual(response.status_code, 302)
        suivi = Suivi.objects.get(beneficiaire=self.beneficiaire_eftp)
        self.assertEqual(suivi.situation_actuelle, "")
        self.assertEqual(suivi.type_contrat, "")

    def test_liste_scopee(self):
        Suivi.objects.create(
            beneficiaire=self.beneficiaire_inap, vague="m3", date_suivi=date(2026, 4, 1), issue_contact="joint",
        )
        self.client.force_login(self.saisie_eftp)
        liste = self.client.get(reverse("suivis:liste"))
        self.assertEqual(len(liste.context["suivis"]), 0)
