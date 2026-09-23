from django.db import models


class Certification(models.Model):
    beneficiaire = models.ForeignKey(
        "beneficiaires.Beneficiaire", on_delete=models.CASCADE, related_name="certifications",
        verbose_name="Bénéficiaire",
    )
    type_certificat = models.CharField("Type de certificat", max_length=150)
    date_certification = models.DateField("Date de certification")

    class Meta:
        ordering = ["-date_certification"]

    def __str__(self):
        return f"{self.beneficiaire_id} - {self.type_certificat}"
