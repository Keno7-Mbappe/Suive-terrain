from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.referentiels.models import Institution

from .models import Profile

"""Ces tests exercent les mixins de permission/scoping (apps/comptes/mixins.py,
apps/comptes/forms.py) au travers des vues bénéficiaires, qui sont les premières
à les utiliser. Ils reproduisent - sous forme automatisée - les vérifications
faites manuellement en curl pendant le développement (login, création, 403 par
rôle, cloisonnement par institution)."""


class ScopingParInstitutionEtRoleTests(TestCase):
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

        self.saisie_eftp = self._creer_utilisateur("saisie_eftp", "saisie", self.eftp)
        self.validateur = self._creer_utilisateur("validateur", "validateur", None)
        self.consultation = self._creer_utilisateur("consultation", "consultation", None)

    @staticmethod
    def _creer_utilisateur(username, role, institution):
        user = User.objects.create_user(username=username, password="motdepasse123")
        Profile.objects.filter(user=user).update(role=role, institution=institution)
        return user

    def test_anonyme_redirige_vers_login(self):
        response = self.client.get(reverse("beneficiaires:liste"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_saisie_ne_voit_que_les_beneficiaires_de_son_institution(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.get(reverse("beneficiaires:liste"))
        beneficiaires = list(response.context["beneficiaires"])
        self.assertIn(self.beneficiaire_eftp, beneficiaires)
        self.assertNotIn(self.beneficiaire_inap, beneficiaires)

    def test_administrateur_voit_toutes_les_institutions(self):
        admin = self._creer_utilisateur("admin_test", "administrateur", None)
        self.client.force_login(admin)
        response = self.client.get(reverse("beneficiaires:liste"))
        beneficiaires = list(response.context["beneficiaires"])
        self.assertIn(self.beneficiaire_eftp, beneficiaires)
        self.assertIn(self.beneficiaire_inap, beneficiaires)

    def test_consultation_ne_peut_pas_creer(self):
        self.client.force_login(self.consultation)
        response = self.client.get(reverse("beneficiaires:creer"))
        self.assertEqual(response.status_code, 403)

    def test_saisie_peut_creer(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.get(reverse("beneficiaires:creer"))
        self.assertEqual(response.status_code, 200)

    def test_validateur_ne_peut_pas_creer_mais_peut_modifier(self):
        self.client.force_login(self.validateur)
        self.assertEqual(self.client.get(reverse("beneficiaires:creer")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("beneficiaires:modifier", args=[self.beneficiaire_eftp.pk])).status_code, 200
        )

    def test_institution_verrouillee_a_la_creation_meme_si_falsifiee(self):
        self.client.force_login(self.saisie_eftp)
        reponse = self.client.post(reverse("beneficiaires:creer"), {
            "nom": "Houmed", "prenom": "Warsama", "sexe": "M", "date_naissance": "2001-05-05",
            "region": "arta", "institution": self.inap.pk,  # tentative de forcer une autre institution
            "date_enregistrement": "2026-09-06", "statut": "actif",
        })
        self.assertEqual(reponse.status_code, 302)
        nouveau = Beneficiaire.objects.get(nom="Houmed")
        self.assertEqual(nouveau.institution_id, self.eftp.pk)

    def test_saisie_ne_peut_pas_modifier_un_beneficiaire_dune_autre_institution(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.get(reverse("beneficiaires:modifier", args=[self.beneficiaire_inap.pk]))
        self.assertEqual(response.status_code, 404)
