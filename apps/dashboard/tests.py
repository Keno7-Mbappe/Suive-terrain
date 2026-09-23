from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.beneficiaires.models import Beneficiaire
from apps.certifications.models import Certification
from apps.comptes.models import Profile
from apps.formations.models import Formation
from apps.insertions.models import Insertion
from apps.referentiels.models import Institution

from .views import _compter_anomalies


def _beneficiaire(institution, **kwargs):
    defaults = {
        "nom": "Test", "prenom": "Test", "sexe": "M", "date_naissance": date(2000, 1, 1),
        "region": "djibouti", "institution": institution,
    }
    defaults.update(kwargs)
    return Beneficiaire.objects.create(**defaults)


class AnomaliesTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(libelle="EFTP", type="eftp", region="djibouti")

    def test_aucune_anomalie_sur_un_parcours_coherent(self):
        b = _beneficiaire(self.institution, date_naissance=date(2000, 1, 1), date_enregistrement=date(2026, 1, 1))
        Formation.objects.create(beneficiaire=b, domaine="Informatique", date_debut=date(2025, 1, 1))
        Certification.objects.create(beneficiaire=b, type_certificat="Certificat", date_certification=date(2025, 7, 1))
        Insertion.objects.create(beneficiaire=b, situation_prof="emploi_salarie", date_insertion=date(2025, 9, 1))
        self.assertEqual(_compter_anomalies(Beneficiaire.objects.all()), 0)

    def test_insertion_avant_le_debut_de_la_formation_est_une_anomalie(self):
        b = _beneficiaire(self.institution, date_naissance=date(2000, 1, 1), date_enregistrement=date(2026, 1, 1))
        Formation.objects.create(beneficiaire=b, domaine="Informatique", date_debut=date(2025, 6, 1))
        Insertion.objects.create(beneficiaire=b, situation_prof="emploi_salarie", date_insertion=date(2025, 1, 1))
        self.assertEqual(_compter_anomalies(Beneficiaire.objects.all()), 1)

    def test_certification_avant_le_debut_de_la_formation_est_une_anomalie(self):
        b = _beneficiaire(self.institution, date_naissance=date(2000, 1, 1), date_enregistrement=date(2026, 1, 1))
        Formation.objects.create(beneficiaire=b, domaine="Informatique", date_debut=date(2025, 6, 1))
        Certification.objects.create(beneficiaire=b, type_certificat="Certificat", date_certification=date(2025, 1, 1))
        self.assertEqual(_compter_anomalies(Beneficiaire.objects.all()), 1)

    def test_age_implausible_est_une_anomalie(self):
        _beneficiaire(self.institution, date_naissance=date(2020, 1, 1), date_enregistrement=date(2026, 1, 1))  # 6 ans
        self.assertEqual(_compter_anomalies(Beneficiaire.objects.all()), 1)


class DashboardViewsTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(libelle="EFTP", type="eftp", region="djibouti")
        self.admin = User.objects.create_user(username="admin_test", password="motdepasse123")
        Profile.objects.filter(user=self.admin).update(role="administrateur")

    def test_dashboard_public_accessible_sans_connexion(self):
        response = self.client.get(reverse("dashboard:public"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Qualité des données")

    def test_dashboard_interne_expose_le_panneau_qualite(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qualité des données")

    def test_taux_completude_avec_coordonnees_partielles(self):
        _beneficiaire(self.institution, telephone="77000000", email="")
        _beneficiaire(self.institution, telephone="77000001", email="test@example.com")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["taux_completude"], 50.0)
