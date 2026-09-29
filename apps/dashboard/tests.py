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
        self.institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")

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
        self.institution = Institution.objects.create(libelle="DGFP", type="dgfp", region="djibouti")
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

    def test_taux_completude_mesure_la_joignabilite_par_telephone(self):
        _beneficiaire(self.institution, telephone="77000000", email="")
        _beneficiaire(self.institution, telephone="", email="test@example.com")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.context["taux_completude"], 50.0)

    def test_dashboard_sans_donnees_affiche_les_etats_vides(self):
        response = self.client.get(reverse("dashboard:public"))
        self.assertEqual(response.context["total_beneficiaires"], 0)
        self.assertContains(response, "Pas encore de réponses")
        self.assertContains(response, "Pas encore d'insertions")

    def test_filtres_non_numeriques_sont_ignores(self):
        response = self.client.get(reverse("dashboard:public"), {"cycle": "abc", "institution": "1; DROP TABLE"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filtre_cycle"], "")
        self.assertEqual(response.context["filtre_institution"], "")

    def test_parcours_et_taux_de_passage(self):
        formee = _beneficiaire(self.institution, nom="Formee", sexe="F")
        _beneficiaire(self.institution, nom="Inscrit")
        Formation.objects.create(
            beneficiaire=formee, domaine="Informatique", date_debut=date(2025, 1, 1), statut_formation="achevee"
        )
        Certification.objects.create(beneficiaire=formee, type_certificat="Certificat", date_certification=date(2025, 7, 1))
        response = self.client.get(reverse("dashboard:public"))
        tunnel = {etape["libelle"]: etape for etape in response.context["tunnel"]}
        self.assertEqual([tunnel[k]["valeur"] for k in ("Inscrits", "Formés", "Certifiés", "Insérés")], [2, 1, 1, 0])
        self.assertEqual(tunnel["Formés"]["conversion"], 50.0)
        self.assertEqual(tunnel["Certifiés"]["conversion"], 100.0)
        self.assertEqual(response.context["sexe"]["femmes"], 1)

    def test_pages_declarent_un_viewport_adapte_aux_telephones(self):
        for url in (reverse("dashboard:public"), reverse("login")):
            self.assertContains(self.client.get(url), 'name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"')

    def test_menu_mobile_present_partout_mais_navigation_adaptee_au_role(self):
        # Le même habillage (menu en tiroir sur téléphone) sert la vue publique et la
        # vue interne, pour qu'elles se ressemblent — seul le contenu du menu change.
        self.client.force_login(self.admin)
        interne = self.client.get(reverse("dashboard:index"))
        self.assertContains(interne, 'id="menu-bouton"')
        self.assertContains(interne, 'aria-controls="menu-lateral"')
        self.assertContains(interne, 'id="menu-lateral"')
        self.assertContains(interne, "Bénéficiaires")
        self.client.logout()
        publique = self.client.get(reverse("dashboard:public"))
        self.assertContains(publique, 'id="menu-bouton"')
        self.assertContains(publique, 'id="menu-lateral"')
        self.assertContains(publique, "Espace institutions")
        # "Bénéficiaires" reste un intitulé d'indicateur légitime sur le tableau de bord
        # public (nombre de bénéficiaires) : ce qui distingue la navigation, c'est le lien
        # vers la liste nominative, réservé à l'espace connecté.
        self.assertNotContains(publique, 'href="/beneficiaires/"')
        self.assertContains(interne, 'href="/beneficiaires/"')

    def test_page_de_connexion_sans_coque_applicative(self):
        # La connexion reste un simple écran centré : le menu existe dans le HTML (même
        # coque que le reste de l'application) mais la classe .page-connexion le masque
        # entièrement en CSS, puisqu'il n'y a rien à y naviguer avant de s'authentifier.
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'class="page-connexion"')
        self.assertContains(response, 'class="login-wrapper"')

    def test_dashboard_public_n_expose_aucune_donnee_nominative(self):
        _beneficiaire(self.institution, nom="Nomtresspecifique", prenom="Prenomtresspecifique")
        response = self.client.get(reverse("dashboard:public"))
        self.assertNotContains(response, "Nomtresspecifique")
        self.assertNotContains(response, "Prenomtresspecifique")
