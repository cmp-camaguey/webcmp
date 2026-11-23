from django.db import migrations


def seed_procedures(apps, schema_editor):
    ComplianceProcedure = apps.get_model('core', 'ComplianceProcedure')
    defaults = [
        (
            'incident_response',
            'Notificación de incidentes de ciberseguridad',
            (
                'Este procedimiento describe cómo se notifican y gestionan los incidentes de '
                'ciberseguridad que afecten datos personales.\n\n'
                'Completar con:\n'
                '- Responsable y equipo de respuesta.\n'
                '- Canales internos de reporte.\n'
                '- Plazos de notificación.\n'
                '- Autoridades o partes a notificar.\n'
                '- Registro y seguimiento del incidente.'
            ),
        ),
        (
            'backup_restore',
            'Respaldo y restauración de bases de datos',
            (
                'Este procedimiento describe cómo se realizan los respaldos de bases de datos '
                'con datos personales y cómo se verifica su restauración.\n\n'
                'Completar con:\n'
                '- Frecuencia y alcance de los respaldos.\n'
                '- Ubicación y protección de las copias.\n'
                '- Responsable de la ejecución y verificación.\n'
                '- Pruebas periódicas de restauración.\n'
                '- Evidencia de la última prueba realizada.'
            ),
        ),
    ]
    for procedure_type, title, body in defaults:
        ComplianceProcedure.objects.get_or_create(
            procedure_type=procedure_type,
            defaults={'title': title, 'body': body, 'is_published': False},
        )


def unseed_procedures(apps, schema_editor):
    ComplianceProcedure = apps.get_model('core', 'ComplianceProcedure')
    ComplianceProcedure.objects.filter(
        procedure_type__in=['incident_response', 'backup_restore']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0018_add_compliance_procedure'),
    ]

    operations = [
        migrations.RunPython(seed_procedures, unseed_procedures),  # data-safety: reviewed: seeds two default compliance procedure placeholders; reverse removes only those seeded records
    ]
