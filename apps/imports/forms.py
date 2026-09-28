from django import forms

from .schemas import sections_pour, vague_suggeree
from .services import _get_beneficiaire, institution_de_soumission


def nom_champ_formulaire(cle_kobo):
    """« selection/canal » -> « selection__canal » (le « / » n'est pas un nom de champ sûr)."""
    return cle_kobo.replace("/", "__")


class SoumissionCorrectionForm(forms.Form):
    """Formulaire de correction généré à partir de la description des champs Kobo
    (schemas.py) : présente toutes les réponses de la soumission, prêtes à être
    modifiées, et fabrique la version corrigée à intégrer."""

    def __init__(self, *args, soumission, **kwargs):
        self.soumission = soumission
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        donnees = soumission.donnees_effectives
        self._champs_kobo = {}
        self._noms_par_section = []
        for titre, champs in sections_pour(soumission.type_formulaire):
            noms = []
            for champ in champs:
                nom = nom_champ_formulaire(champ.cle)
                valeur = donnees.get(champ.cle)
                if champ.cle == "module_suivi/vague" and not valeur:
                    valeur = vague_suggeree(donnees)
                self.fields[nom] = self._construire_champ(champ, valeur)
                if champ.type == "choix_multiple":
                    self.initial[nom] = str(valeur or "").split()
                else:
                    self.initial[nom] = "" if valeur is None else valeur
                self._champs_kobo[nom] = champ
                noms.append(nom)
            self._noms_par_section.append((titre, noms))

    @staticmethod
    def _construire_champ(champ, valeur_actuelle):
        options = {"label": champ.libelle, "required": champ.obligatoire}
        if champ.type == "texte":
            return forms.CharField(**options)
        if champ.type == "texte_long":
            return forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **options)
        if champ.type == "date":
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), **options)
        if champ.type == "entier":
            return forms.IntegerField(min_value=0, **options)
        choix = [(str(code), libelle) for code, libelle in champ.choix]
        codes_connus = {code for code, _ in choix}
        if champ.type == "choix_multiple":
            inconnus = [c for c in str(valeur_actuelle or "").split() if c not in codes_connus]
            choix += [(c, f"{c} (valeur inconnue)") for c in inconnus]
            options["required"] = False
            return forms.MultipleChoiceField(choices=choix, widget=forms.CheckboxSelectMultiple, **options)
        if valeur_actuelle and str(valeur_actuelle) not in codes_connus:
            choix.append((str(valeur_actuelle), f"{valeur_actuelle} (valeur inconnue)"))
        return forms.ChoiceField(choices=[("", "—")] + choix, **options)

    @property
    def sections(self):
        return [(titre, [self[nom] for nom in noms]) for titre, noms in self._noms_par_section]

    def clean(self):
        cleaned = super().clean()
        if self.soumission.type_formulaire == "suivi":
            identifiant = cleaned.get("selection__id_beneficiaire")
            if identifiant and _get_beneficiaire(identifiant) is None:
                self.add_error("selection__id_beneficiaire", "Aucun bénéficiaire avec cet identifiant dans la base.")
        return cleaned

    def enregistrer(self):
        """Écrit la version corrigée (sans jamais toucher aux données brutes de Kobo)."""
        donnees = dict(self.soumission.donnees_effectives)
        for nom, champ in self._champs_kobo.items():
            valeur = self.cleaned_data.get(nom)
            if champ.type == "choix_multiple":
                valeur = " ".join(valeur or [])
            elif hasattr(valeur, "isoformat"):
                valeur = valeur.isoformat()
            elif isinstance(valeur, int):
                valeur = str(valeur)
            if valeur in (None, ""):
                donnees.pop(champ.cle, None)  # Kobo n'envoie pas les réponses vides
            else:
                donnees[champ.cle] = valeur

        if self.soumission.type_formulaire == "suivi":
            beneficiaire = _get_beneficiaire(donnees.get("selection/id_beneficiaire"))
            if beneficiaire:
                # Le rappel affiché à l'enquêteur suit le bénéficiaire réellement retenu.
                donnees["selection/nom_prenom"] = f"{beneficiaire.prenom} {beneficiaire.nom}".strip()
                donnees["selection/institution"] = beneficiaire.institution.libelle
                donnees["selection/region"] = beneficiaire.get_region_display()

        soumission = self.soumission
        soumission.donnees_corrigees = donnees
        soumission.institution = institution_de_soumission(soumission.type_formulaire, donnees)
        soumission.statut = "nouveau"  # à revalider avec les corrections
        soumission.erreur = ""
        soumission.save(update_fields=["donnees_corrigees", "institution", "statut", "erreur"])
        return soumission
