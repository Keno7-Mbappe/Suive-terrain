class InstitutionScopedBeneficiaireFormMixin:
    """ModelForm mixin: restricts the `beneficiaire` field's choices to the
    requester's institution (saisie/validateur scoped to one institution).
    Users without an institution (administrateur, ONEQ, Direction des Projets)
    see every beneficiaire.
    """

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(request.user, "profile", None) if request else None
        if "beneficiaire" in self.fields and profile and profile.institution_id:
            self.fields["beneficiaire"].queryset = self.fields["beneficiaire"].queryset.filter(
                institution_id=profile.institution_id
            )
