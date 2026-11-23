from django.db import migrations

INCIDENT_BODY = """<h4>Responsable</h4>
<p>[Nombre y cargo del responsable del procedimiento]</p>
<h4>Canales de reporte</h4>
<ul>
  <li><strong>Correo:</strong> [correo institucional]</li>
  <li><strong>Teléfono:</strong> [teléfono de contacto]</li>
  <li><strong>Canal interno:</strong> [sistema o vía interna de reporte]</li>
</ul>
<h4>Plazos de notificación</h4>
<p>[Indicar plazos internos y externos de notificación]</p>
<h4>Autoridades o partes a notificar</h4>
<p>[Indicar autoridades, titulares u otras partes según corresponda]</p>
<h4>Registro y seguimiento</h4>
<p>[Indicar dónde se documenta el incidente, las acciones tomadas y su cierre]</p>"""

BACKUP_BODY = """<h4>Alcance y frecuencia</h4>
<p>[Indicar qué bases de datos se respaldan y con qué frecuencia]</p>
<h4>Ubicación y protección</h4>
<p>[Indicar dónde se almacenan las copias y cómo se protegen]</p>
<h4>Responsable</h4>
<p>[Nombre y cargo del responsable de ejecución y verificación]</p>
<h4>Pruebas de restauración</h4>
<ul>
  <li><strong>Periodicidad:</strong> [cada cuánto se prueba]</li>
  <li><strong>Última prueba:</strong> [fecha]</li>
  <li><strong>Resultado:</strong> [resultado o evidencia]</li>
</ul>"""


def update_examples(apps, schema_editor):
    ComplianceProcedure = apps.get_model('core', 'ComplianceProcedure')
    updates = {
        'incident_response': (
            'Notificación de incidentes de ciberseguridad',
            INCIDENT_BODY,
        ),
        'backup_restore': (
            'Respaldo y restauración de bases de datos',
            BACKUP_BODY,
        ),
    }
    for procedure_type, (title, body) in updates.items():
        procedure = ComplianceProcedure.objects.filter(procedure_type=procedure_type).first()
        if not procedure:
            continue
        if procedure.body and 'Completar con:' not in procedure.body and '<h4>' in procedure.body:
            continue
        procedure.title = title
        procedure.body = body
        procedure.save(update_fields=['title', 'body', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0019_seed_compliance_procedures'),
    ]

    operations = [
        migrations.RunPython(update_examples, migrations.RunPython.noop),  # data-safety: reviewed: updates only seeded placeholder compliance procedure bodies; skips already customized content
    ]
