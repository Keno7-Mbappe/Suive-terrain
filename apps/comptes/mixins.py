from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """CBV mixin: restrict a view to users whose profile role is in `allowed_roles`.
    Administrateur always passes. Set `allowed_roles` on the view class.
    """

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        profile = getattr(request.user, "profile", None)
        if profile is None or (profile.role not in self.allowed_roles and profile.role != "administrateur"):
            raise PermissionDenied("Vous n'avez pas les droits pour accéder à cette page.")
        return super().dispatch(request, *args, **kwargs)


class InstitutionScopedQuerysetMixin:
    """CBV mixin: restrict the queryset to the requester's institution, following
    the FK path given by `institution_lookup` (e.g. "institution" or
    "beneficiaire__institution"). Users without an institution (administrateur,
    ONEQ, Direction des Projets) see everything.
    """

    institution_lookup = "institution"

    def get_queryset(self):
        queryset = super().get_queryset()
        profile = getattr(self.request.user, "profile", None)
        if profile is None or profile.institution_id is None:
            return queryset
        return queryset.filter(**{self.institution_lookup: profile.institution_id})


class InstitutionScopedFormMixin:
    """FormView/CreateView/UpdateView mixin: pass the request to the form so it
    can scope its `beneficiaire` (or other) ModelChoiceField querysets.

    Also drops the trailing "\xa0:" Django appends to every field label - a
    form-level `label_suffix = ""` class attribute is silently ignored by
    Django (BaseForm.__init__ hardcodes `_(":")` as its fallback rather than
    reading a class attribute), so it must be passed as a constructor kwarg.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["label_suffix"] = ""
        return kwargs
