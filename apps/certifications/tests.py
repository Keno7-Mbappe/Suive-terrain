from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.comptes.models import Profile
from apps.referentiels.models import Institution

from .models import Certification


class CertificationScopingTests(TestCase):
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
        response = self.client.get(reverse("certifications:creer"))
        choix = list(response.context["form"].fields["beneficiaire"].queryset)
        self.assertIn(self.beneficiaire_eftp, choix)
        self.assertNotIn(self.beneficiaire_inap, choix)

    def test_creation_et_liste_scopee(self):
        self.client.force_login(self.saisie_eftp)
        response = self.client.post(reverse("certifications:creer"), {
            "beneficiaire": self.beneficiaire_eftp.pk, "type_certificat": "CAP Informatique",
            "date_certification": "2026-06-15",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Certification.objects.filter(beneficiaire=self.beneficiaire_eftp).count(), 1)

        liste = self.client.get(reverse("certifications:liste"))
        self.assertEqual(len(liste.context["certifications"]), 1)


class CertificationSupprimerViewTests(TestCase):
    def setUp(self):
        self.dgfp = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
        self.inap = Institution.objects.create(libelle="INAP", type="inap", region="djibouti")
        self.beneficiaire = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=self.dgfp,
        )
        self.certification = Certification.objects.create(
            beneficiaire=self.beneficiaire, type_certificat="CAP Informatique", date_certification=date(2026, 6, 15),
        )
        self.saisie = User.objects.create_user(username="saisie_test", password="motdepasse123")
        Profile.objects.filter(user=self.saisie).update(role="saisie", institution=self.dgfp)
        self.consultation = User.objects.create_user(username="consultation_test", password="motdepasse123")

    def test_supprime_la_certification(self):
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("certifications:supprimer", args=[self.certification.pk]))
        self.assertRedirects(reponse, reverse("certifications:liste"))
        self.assertFalse(Certification.objects.filter(pk=self.certification.pk).exists())

    def test_role_consultation_refuse(self):
        self.client.force_login(self.consultation)
        reponse = self.client.post(reverse("certifications:supprimer", args=[self.certification.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(Certification.objects.filter(pk=self.certification.pk).exists())

    def test_ne_peut_pas_supprimer_une_certification_dune_autre_institution(self):
        beneficiaire_inap = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="djibouti", institution=self.inap,
        )
        certification_inap = Certification.objects.create(
            beneficiaire=beneficiaire_inap, type_certificat="CAP Couture", date_certification=date(2026, 6, 15),
        )
        self.client.force_login(self.saisie)
        reponse = self.client.post(reverse("certifications:supprimer", args=[certification_inap.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(Certification.objects.filter(pk=certification_inap.pk).exists())
