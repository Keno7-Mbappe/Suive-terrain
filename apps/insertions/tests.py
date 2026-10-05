from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import Institution

from .models import Insertion


class InsertionScopingTests(TestCase):
    def setUp(self):
        self.eftp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
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
        response = self.client.get(reverse("insertions:creer"))
        choix = list(response.context["form"].fields["beneficiaire"].queryset)
        self.assertIn(self.beneficiaire_eftp, choix)
        self.assertNotIn(self.beneficiaire_inap, choix)

    def test_creation_et_liste_scopee(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.post(reverse("insertions:creer"), {
            "beneficiaire": self.beneficiaire_eftp.pk, "situation_prof": "emploi_salarie",
            "date_insertion": "2026-07-01", "delai_insertion_mois": 3,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Insertion.objects.filter(beneficiaire=self.beneficiaire_eftp).count(), 1)

        liste = self.client.get(reverse("insertions:liste"))
        self.assertEqual(len(liste.context["insertions"]), 1)


class InsertionSupprimerViewTests(TestCase):
    def setUp(self):
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.dgfp,
        )
        self.insertion = Insertion.objects.create(beneficiaire=self.beneficiaire, situation_prof="emploi_salarie")
        self.saisie = User.objects.create_user(username="saisie_test", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie", institution=self.dgfp)
        self.consultation = User.objects.create_user(username="consultation_test", password="motdepasse123")

    def test_supprime_linsertion(self):
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("insertions:supprimer", args=[self.insertion.pk]))
        self.assertRedirects(reponse, reverse("insertions:liste"))
        self.assertFalse(Insertion.objects.filter(pk=self.insertion.pk).exists())

    def test_role_consultation_refuse(self):
        self.client.force_login(self.consultation)
        reponse = self.client.post(reverse("insertions:supprimer", args=[self.insertion.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(Insertion.objects.filter(pk=self.insertion.pk).exists())

    def test_ne_peut_pas_supprimer_une_insertion_dune_autre_institution(self):
        beneficiaire_inap = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="djibouti", institution=self.inap,
        )
        insertion_inap = Insertion.objects.create(beneficiaire=beneficiaire_inap, situation_prof="auto_emploi")
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("insertions:supprimer", args=[insertion_inap.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(Insertion.objects.filter(pk=insertion_inap.pk).exists())


class InsertionListViewFiltresTests(TestCase):
    def setUp(self):
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.beneficiaire1 = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.dgfp,
        )
        self.beneficiaire2 = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="djibouti", institution=self.dgfp,
        )
        Insertion.objects.create(beneficiaire=self.beneficiaire1, situation_prof="emploi_salarie")
        Insertion.objects.create(beneficiaire=self.beneficiaire2, situation_prof="en_recherche")
        self.utilisateur = User.objects.create_user(username="consultante", password="motdepasse123")
        self.client.force_login(self.utilisateur)

    def test_recherche_par_nom_du_beneficiaire(self):
        reponse = self.client.get(reverse("insertions:liste"), {"q": "amina"})
        self.assertEqual(
            [i.beneficiaire_id for i in reponse.context["insertions"]], [self.beneficiaire1.pk]
        )

    def test_filtre_par_situation(self):
        reponse = self.client.get(reverse("insertions:liste"), {"situation": "en_recherche"})
        self.assertEqual(
            [i.beneficiaire_id for i in reponse.context["insertions"]], [self.beneficiaire2.pk]
        )
