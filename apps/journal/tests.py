from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import Institution

from .models import Modification


class JournalisationTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.validateur = User.objects.create_user(username="valid_journal", password="motdepasse123")
        Profile.objects.filter(user=self.validateur).update(role="validateur")
        self.saisie = User.objects.create_user(username="saisie_journal_ok", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie")

    def test_creation_est_journalisee_avec_lutilisateur_courant(self):
        self.client.force_login(self.saisie)
        self.client.post(reverse("beneficiaires:creer"), {
            "nom": "Ali", "prenom": "Amina", "sexe": "F", "date_naissance": "1999-03-01",
            "region": "djibouti", "institution": self.institution.pk, "date_enregistrement": "2026-01-01",
            "statut": "actif",
        })
        entree = Modification.objects.filter(modele="Beneficiaire", action="creation").first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.utilisateur, self.saisie)
        self.assertIn("Amina", entree.objet_repr)

    def test_modification_liste_les_champs_changes(self):
        beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.institution,
        )
        Modification.objects.all().delete()  # ne garder que la modification testée ici
        self.client.force_login(self.validateur)
        self.client.post(reverse("beneficiaires:modifier", args=[beneficiaire.pk]), {
            "nom": "Ali", "prenom": "Amina", "sexe": "F", "date_naissance": "1999-03-01",
            "region": "arta", "institution": self.institution.pk, "date_enregistrement": "2026-01-01",
            "statut": "actif",
        })
        entree = Modification.objects.filter(modele="Beneficiaire", action="modification").first()
        self.assertIsNotNone(entree)
        self.assertIn("Région", entree.details)

    def test_suppression_est_journalisee(self):
        beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.institution,
        )
        reference = str(beneficiaire)
        beneficiaire.delete()
        entree = Modification.objects.filter(modele="Beneficiaire", action="suppression").first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.objet_repr, reference)

    def test_liste_reservee_aux_validateurs(self):
        simple = User.objects.create_user(username="saisie_journal", password="motdepasse123")
        Profile.objects.filter(user=simple).update(role="saisie")
        self.client.force_login(simple)
        self.assertEqual(self.client.get(reverse("journal:liste")).status_code, 403)

        self.client.force_login(self.validateur)
        self.assertEqual(self.client.get(reverse("journal:liste")).status_code, 200)
