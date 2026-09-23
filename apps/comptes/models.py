from django.conf import settings
from django.db import models

ROLES = [
    ("administrateur", "Administrateur"),
    ("saisie", "Saisie"),
    ("validateur", "Validateur"),
    ("consultation", "Consultation"),
]


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile", verbose_name="Compte utilisateur"
    )
    role = models.CharField("Rôle", max_length=20, choices=ROLES, default="consultation")
    institution = models.ForeignKey(
        "referentiels.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="utilisateurs",
        verbose_name="Institution de rattachement",
        help_text="Institution de rattachement. Laisser vide pour un accès multi-institutions (administrateur, ONEQ, Direction des Projets).",
    )

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_administrateur(self):
        return self.role == "administrateur"

    @property
    def is_validateur(self):
        return self.role in ("administrateur", "validateur")

    @property
    def is_saisie(self):
        return self.role in ("administrateur", "saisie")
