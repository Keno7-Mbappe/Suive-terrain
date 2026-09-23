from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to users whose profile role is in `roles`.
    Administrateur always passes.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if profile is None or (profile.role not in roles and profile.role != "administrateur"):
                raise PermissionDenied("Vous n'avez pas les droits pour accéder à cette page.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def scope_queryset_to_institution(request, queryset, institution_field="institution"):
    """Restrict a queryset to the requester's institution unless they are
    administrateur/ONEQ/Direction des Projets (profile.institution is None = accès global).
    """
    profile = getattr(request.user, "profile", None)
    if profile is None or profile.institution_id is None:
        return queryset
    return queryset.filter(**{institution_field: profile.institution_id})
