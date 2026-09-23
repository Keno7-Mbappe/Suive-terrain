from datetime import date

from django.test import TestCase

from apps.referentiels.models import Institution

from .models import Beneficiaire, SequenceAnnuelle


def _institution(libelle="EFTP"):
    return Institution.objects.create(libelle=libelle, type="eftp", region="djibouti")


class GenerationIdentifiantTests(TestCase):
    def test_premier_beneficiaire_de_lannee(self):
        b = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=_institution(), date_enregistrement=date(2026, 1, 15),
        )
        self.assertEqual(b.id_beneficiaire, "B-2026-0001")

    def test_incrementation_sequentielle_sur_la_meme_annee(self):
        institution = _institution()
        premier = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution, date_enregistrement=date(2026, 1, 15),
        )
        second = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="arta", institution=institution, date_enregistrement=date(2026, 6, 1),
        )
        self.assertEqual(premier.id_beneficiaire, "B-2026-0001")
        self.assertEqual(second.id_beneficiaire, "B-2026-0002")

    def test_compteur_reparti_par_annee(self):
        institution = _institution()
        Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution, date_enregistrement=date(2026, 12, 31),
        )
        b_2027 = Beneficiaire.objects.create(
            nom="Omar", prenom="Yasin", sexe="M", date_naissance=date(1998, 7, 20),
            region="arta", institution=institution, date_enregistrement=date(2027, 1, 1),
        )
        self.assertEqual(b_2027.id_beneficiaire, "B-2027-0001")
        self.assertEqual(SequenceAnnuelle.objects.get(annee=2026).dernier_numero, 1)

    def test_identifiant_non_regenere_a_la_mise_a_jour(self):
        b = Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=_institution(), date_enregistrement=date(2026, 1, 15),
        )
        identifiant_initial = b.id_beneficiaire
        b.statut = "abandon"
        b.save()
        self.assertEqual(b.id_beneficiaire, identifiant_initial)


class DatesSaisiesEnChaineTests(TestCase):
    """Les imports (Excel, Kobo) fournissent les dates en chaînes ISO plutôt qu'en
    objets `date` - save() doit les normaliser sans planter (cf. bug corrigé)."""

    def test_creation_avec_dates_en_chaine(self):
        b = Beneficiaire.objects.create(
            nom="Awaleh", prenom="Fatouma", sexe="F", date_naissance="1995-01-01",
            region="arta", institution=_institution(), date_enregistrement="2026-09-06",
        )
        self.assertEqual(b.date_naissance, date(1995, 1, 1))
        self.assertEqual(b.tranche_age, "31-40")


class TrancheAgeTests(TestCase):
    def _beneficiaire_avec_age(self, naissance, enregistrement):
        return Beneficiaire.objects.create(
            nom="Test", prenom="Test", sexe="M", date_naissance=naissance,
            region="djibouti", institution=_institution(f"Inst-{naissance}"),
            date_enregistrement=enregistrement,
        )

    def test_tranches(self):
        cas = [
            (date(2010, 1, 1), date(2026, 1, 1), "<20"),
            (date(2000, 1, 1), date(2026, 1, 1), "20-30"),
            (date(1990, 1, 1), date(2026, 1, 1), "31-40"),
            (date(1980, 1, 1), date(2026, 1, 1), "41-50"),
            (date(1960, 1, 1), date(2026, 1, 1), ">50"),
        ]
        for naissance, enregistrement, attendu in cas:
            with self.subTest(naissance=naissance):
                b = self._beneficiaire_avec_age(naissance, enregistrement)
                self.assertEqual(b.tranche_age, attendu)

    def test_anniversaire_pas_encore_atteint_dans_lannee(self):
        # Né le 10 juin, enregistré le 1er juin de la même année où il fête ses 30 ans :
        # l'anniversaire n'est pas encore passé, l'âge retenu doit être 29 (tranche 20-30) et non 30.
        b = self._beneficiaire_avec_age(date(1996, 6, 10), date(2026, 6, 1))
        self.assertEqual(b.tranche_age, "20-30")


class DoublonsTests(TestCase):
    def test_detecte_un_doublon_nom_prenom_naissance(self):
        institution = _institution()
        Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution,
        )
        doublons = Beneficiaire.trouver_doublons_potentiels("ali", "AMINA", date(1999, 3, 1))
        self.assertEqual(doublons.count(), 1)

    def test_pas_de_doublon_si_date_naissance_differente(self):
        institution = _institution()
        Beneficiaire.objects.create(
            nom="Ali", prenom="Amina", sexe="F", date_naissance=date(1999, 3, 1),
            region="djibouti", institution=institution,
        )
        doublons = Beneficiaire.trouver_doublons_potentiels("Ali", "Amina", date(2000, 1, 1))
        self.assertEqual(doublons.count(), 0)
