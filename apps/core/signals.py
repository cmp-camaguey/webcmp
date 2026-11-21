"""Señales para notificaciones automáticas de solicitudes ARCO/ARCOP."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import DataSubjectRequest
from apps.core.tasks import send_email_task


@receiver(post_save, sender=DataSubjectRequest)
def notify_data_subject_request(sender, instance, created, **kwargs):
    """
    Envía notificaciones por email cuando se crea o actualiza una solicitud de derechos.

    - Al crear: notifica al admin y envía confirmación al solicitante
    - Al cambiar estado a COMPLETADA/RECHAZADA: notifica al solicitante
    """
    if created:
        _notify_admin_new_request(instance)
        _notify_requester_confirmation(instance)
    else:
        # Verificar si cambió el estado a un estado final
        if instance.tracker.has_changed('status'):
            new_status = instance.status
            if new_status in (
                DataSubjectRequest.Status.COMPLETADA,
                DataSubjectRequest.Status.RECHAZADA,
            ):
                _notify_requester_resolution(instance)


def _notify_admin_new_request(request_obj):
    """Notifica a los superusuarios sobre una nueva solicitud."""
    from django.urls import reverse

    from apps.core.models import Notification
    from apps.core.notifications import make_dedupe_key, notify_superusers

    notify_superusers(
        source='data_subject_request',
        severity=Notification.Severity.INFO,
        title=f'Nueva solicitud de derechos: {request_obj.get_request_type_display()}',
        body=(
            f'Solicitante: {request_obj.subject_name} ({request_obj.subject_email})\n'
            f'Documento: {request_obj.subject_document or "No proporcionado"}\n'
            f'Descripción: {request_obj.description[:200]}'
        ),
        url=reverse('core:data_subject_request_update', args=[request_obj.pk]),
        dedupe_key=make_dedupe_key('data_subject_request', 'new', request_obj.uuid),
    )


def _notify_requester_confirmation(request_obj):
    """Envía confirmación de recibo al solicitante."""
    subject = f'Confirmación de su solicitud de {request_obj.get_request_type_display().lower()}'
    request_type = request_obj.get_request_type_display().lower()
    created_at = request_obj.created_at.strftime('%d/%m/%Y %H:%M')
    document = request_obj.subject_document or 'No proporcionado'
    html_message = f"""
    <p>Estimado/a {request_obj.subject_name}:</p>
    <p>Hemos recibido su solicitud de <strong>{request_type}</strong>
    sobre sus datos personales.</p>
    <p><strong>Detalles de la solicitud:</strong></p>
    <ul>
        <li><strong>Tipo:</strong> {request_obj.get_request_type_display()}</li>
        <li><strong>Correo:</strong> {request_obj.subject_email}</li>
        <li><strong>Documento:</strong> {document}</li>
        <li><strong>Fecha de recepción:</strong> {created_at}</li>
    </ul>
    <p><strong>Descripción:</strong></p>
    <p>{request_obj.description}</p>
    <p>Su solicitud ha sido registrada con el número de referencia:
    <strong>{request_obj.uuid}</strong>.</p>
    <p>Le notificaremos el resultado en un plazo máximo de <strong>30 días hábiles</strong>
    según la normativa vigente (Resolución 58/2022). En casos excepcionales,
    este plazo puede prorrogarse por 30 días hábiles adicionales,
    notificándole la causa.</p>
    <p>Si necesita aportar información adicional, responda a este correo
    citando su número de referencia.</p>
    <hr>
    <p style="font-size: 0.85em; color: #666;">
        Centro Meteorológico Provincial de Camagüey<br>
        Delegado de Protección de Datos: direccion@cmw.insmet.cu
    </p>
    """
    send_email_task(
        subject,
        html_message,
        settings.DEFAULT_FROM_EMAIL,
        [request_obj.subject_email],
    )


def _notify_requester_resolution(request_obj):
    """Notifica al solicitante cuando se resuelve su solicitud."""
    if request_obj.status == DataSubjectRequest.Status.COMPLETADA:
        subject = (
            f'Su solicitud de {request_obj.get_request_type_display().lower()} ha sido completada'
        )
        status_text = 'completada satisfactoriamente'
    else:
        subject = (
            f'Su solicitud de {request_obj.get_request_type_display().lower()} ha sido rechazada'
        )
        status_text = 'rechazada'

    request_type = request_obj.get_request_type_display().lower()
    if request_obj.completed_at:
        completed_at = request_obj.completed_at.strftime('%d/%m/%Y %H:%M')
    else:
        completed_at = 'N/A'
    html_message = f"""
    <p>Estimado/a {request_obj.subject_name}:</p>
    <p>Le informamos que su solicitud de <strong>{request_type}</strong>
    (referencia: <strong>{request_obj.uuid}</strong>) ha sido
    <strong>{status_text}</strong>.</p>
    <p><strong>Detalles:</strong></p>
    <ul>
        <li><strong>Tipo:</strong> {request_obj.get_request_type_display()}</li>
        <li><strong>Estado final:</strong> {request_obj.get_status_display()}</li>
        <li><strong>Fecha de resolución:</strong> {completed_at}</li>
    </ul>
    """
    if request_obj.admin_notes:
        html_message += f"""
        <p><strong>Notas de la resolución:</strong></p>
        <p>{request_obj.admin_notes}</p>
        """
    if request_obj.status == DataSubjectRequest.Status.RECHAZADA:
        html_message += """
        <p>Si no está de acuerdo con esta decisión, puede presentar una reclamación
        ante la autoridad de control competente o contactar con nuestro
        Delegado de Protección de Datos en
        <a href="mailto:direccion@cmw.insmet.cu">direccion@cmw.insmet.cu</a>.</p>
        """
    html_message += """
    <hr>
    <p style="font-size: 0.85em; color: #666;">
        Centro Meteorológico Provincial de Camagüey<br>
        Delegado de Protección de Datos: direccion@cmw.insmet.cu
    </p>
    """
    send_email_task(
        subject,
        html_message,
        settings.DEFAULT_FROM_EMAIL,
        [request_obj.subject_email],
    )
