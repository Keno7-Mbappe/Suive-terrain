# Réalignement du référentiel institutions sur les 3 structures réellement
# suivies : ANEFIP, DGFP (à la place d'EFTP), INAP. ONEQ et la Direction des
# Projets (MENFOP) n'apparaissaient dans aucune donnée réelle (0 bénéficiaire,
# 0 réponse de satisfaction, 0 profil utilisateur, 0 soumission Kobo en
# production au moment de cette migration) : elles sont retirées plutôt que
# simplement masquées, à la demande explicite de l'utilisateur.
from django.db import migrations


def renommer_eftp_et_retirer_oneq_direction_projets(apps, schema_editor):
    Institution = apps.get_model("referentiels", "Institution")
    Institution.objects.filter(type="eftp").update(type="dgfp", libelle="DGFP")
    Institution.objects.filter(type__in=("oneq", "direction_projets")).delete()


def revenir_a_eftp_oneq_direction_projets(apps, schema_editor):
    Institution = apps.get_model("referentiels", "Institution")
    Institution.objects.filter(type="dgfp").update(type="eftp", libelle="EFTP")
    Institution.objects.get_or_create(
        libelle="ONEQ", defaults={"type": "oneq", "region": "djibouti"}
    )
    Institution.objects.get_or_create(
        libelle="Direction des Projets (MENFOP)", defaults={"type": "direction_projets", "region": "djibouti"}
    )


class Migration(migrations.Migration):

    dependencies = [
        ("referentiels", "0003_alter_institution_type"),
    ]

    operations = [
        migrations.RunPython(
            renommer_eftp_et_retirer_oneq_direction_projets,
            revenir_a_eftp_oneq_direction_projets,
        ),
    ]
