from django import forms
from django.contrib import messages
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from apps.core.models import (
    CompanySettings,
    DataSubjectRequest,
    PublicInformationRequest,
    TermsChangeNotice,
)


class VisionView(TemplateView):
    template_name = 'pages/home/institution/vision.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Visión'
        context['parent'] = 'institucion'
        context['segment'] = 'vision'
        return context


class MissionView(TemplateView):
    template_name = 'pages/home/institution/mission.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Misión'
        context['parent'] = 'institucion'
        context['segment'] = 'mision'
        return context


class AboutView(TemplateView):
    template_name = 'pages/home/institution/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Quiénes Somos'
        context['parent'] = 'institucion'
        context['segment'] = 'quienes_somos'
        return context


class TermsChangeNoticeMixin:
    terms_notice_segment = None

    def get_terms_change_notices(self):
        today = timezone.localdate()
        qs = TermsChangeNotice.objects.filter(is_published=True, effective_date__gte=today)
        segment = self.terms_notice_segment or getattr(self, 'segment', None)
        if segment:
            qs = qs.filter(affected_document__in=[segment, TermsChangeNotice.AffectedDocument.ALL])
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['terms_change_notices'] = self.get_terms_change_notices()
        return context


class LegalNoticeView(TermsChangeNoticeMixin, TemplateView):
    template_name = 'pages/home/institution/legal_notice.html'
    terms_notice_segment = 'legal_notice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Aviso legal'
        context['parent'] = 'institucion'
        context['segment'] = 'legal_notice'
        context['company'] = CompanySettings.get_instance()
        return context


class PrivacyPolicyView(TermsChangeNoticeMixin, TemplateView):
    template_name = 'pages/home/institution/privacy_policy.html'
    terms_notice_segment = 'privacy_policy'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Política de privacidad'
        context['parent'] = 'institucion'
        context['segment'] = 'privacy_policy'
        context['company'] = CompanySettings.get_instance()
        return context


class CookiePolicyView(TermsChangeNoticeMixin, TemplateView):
    template_name = 'pages/home/institution/cookie_policy.html'
    terms_notice_segment = 'cookie_policy'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Política de cookies'
        context['parent'] = 'institucion'
        context['segment'] = 'cookie_policy'
        context['company'] = CompanySettings.get_instance()
        return context


class DataSubjectRightsForm(forms.Form):
    """Formulario público para ejercer derechos ARCO/ARCOP."""

    REQUEST_TYPE_CHOICES = DataSubjectRequest.RequestType.choices

    request_type = forms.ChoiceField(
        choices=REQUEST_TYPE_CHOICES,
        label='Derecho que desea ejercer',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=(
            'Seleccione el derecho que desea ejercer: Acceso (saber qué datos tenemos), '
            'Rectificación (corregir datos inexactos), Cancelación (suprimir datos), '
            'Oposición (no tratar sus datos para fines específicos), '
            'Portabilidad (recibir sus datos en formato estructurado).'
        ),
    )
    subject_name = forms.CharField(
        max_length=255,
        label='Nombre completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    subject_email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Recibirá confirmación y actualizaciones en este correo.',
    )
    subject_document = forms.CharField(
        max_length=50,
        required=False,
        label='Documento de identidad (opcional)',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Para verificar su identidad (CI, pasaporte, etc.).',
    )
    description = forms.CharField(
        label='Descripción de la solicitud',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
        help_text=(
            'Describa detalladamente su solicitud: qué datos, qué tratamiento, '
            'qué rectificación o supresión solicita, etc.'
        ),
        min_length=20,
    )

    def clean_subject_email(self):
        """Normalizar email a minúsculas."""
        email = self.cleaned_data['subject_email']
        return email.strip().lower()

    def save(self):
        """Crea la solicitud de derechos y la devuelve."""
        return DataSubjectRequest.objects.create(
            request_type=self.cleaned_data['request_type'],
            subject_email=self.cleaned_data['subject_email'].lower().strip(),
            subject_name=self.cleaned_data['subject_name'].strip(),
            subject_document=self.cleaned_data['subject_document'].strip()
            if self.cleaned_data['subject_document']
            else '',
            description=self.cleaned_data['description'].strip(),
        )


class PublicInformationRequestForm(forms.Form):
    """Formulario público para solicitar información pública."""

    subject_name = forms.CharField(
        max_length=255,
        label='Nombre completo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    subject_email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Recibirá confirmación y actualizaciones en este correo.',
    )
    subject_document = forms.CharField(
        max_length=50,
        required=False,
        label='Documento de identidad (opcional)',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='Para verificar su identidad (CI, pasaporte, etc.).',
    )
    response_format = forms.ChoiceField(
        choices=PublicInformationRequest.ResponseFormat.choices,
        label='Forma de respuesta preferida',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    description = forms.CharField(
        label='Descripción de la información solicitada',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
        help_text=(
            'Indique el tema, el período y, si corresponde, el área o documento concreto '
            'al que se refiere la solicitud.'
        ),
        min_length=20,
    )

    def clean_subject_email(self):
        """Normalizar email a minúsculas."""
        return self.cleaned_data['subject_email'].strip().lower()

    def save(self):
        """Crea la solicitud de información pública y la devuelve."""
        return PublicInformationRequest.objects.create(
            subject_name=self.cleaned_data['subject_name'].strip(),
            subject_email=self.cleaned_data['subject_email'].strip().lower(),
            subject_document=self.cleaned_data['subject_document'].strip()
            if self.cleaned_data['subject_document']
            else '',
            response_format=self.cleaned_data['response_format'],
            description=self.cleaned_data['description'].strip(),
        )


class DataSubjectRightsView(TermsChangeNoticeMixin, FormView):
    """Vista pública para ejercer derechos ARCO/ARCOP."""

    template_name = 'pages/home/institution/data_subject_rights.html'
    form_class = DataSubjectRightsForm
    terms_notice_segment = 'data_subject_rights'
    success_url = '.'  # Recarga la misma página con mensaje de éxito

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ejercicio de derechos ARCO/ARCOP'
        context['parent'] = 'institucion'
        context['segment'] = 'data_subject_rights'
        context['company'] = CompanySettings.get_instance()
        return context

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            'Su solicitud ha sido recibida correctamente. '
            'Le enviaremos un correo de confirmación y le notificaremos '
            'cuando se tramite. El plazo de respuesta es de 30 días hábiles '
            'según la normativa vigente.',
        )
        return super().form_valid(form)


class InstitutionalInformationView(TemplateView):
    template_name = 'pages/home/institution/institutional_information.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Información institucional'
        context['parent'] = 'institucion'
        context['segment'] = 'institutional_information'
        context['company'] = CompanySettings.get_instance()
        return context


class BudgetInformationView(TemplateView):
    template_name = 'pages/home/institution/budget_information.html'

    def get_context_data(self, **kwargs):
        from apps.core.models import BudgetPeriod

        context = super().get_context_data(**kwargs)
        context['title'] = 'Presupuesto'
        context['parent'] = 'institucion'
        context['segment'] = 'institution_budget'
        context['company'] = CompanySettings.get_instance()
        context['budget_periods'] = BudgetPeriod.objects.filter(is_published=True).prefetch_related(
            'lines'
        )
        return context


class AccountabilityInformationView(TemplateView):
    template_name = 'pages/home/institution/accountability_information.html'

    def get_context_data(self, **kwargs):
        from apps.core.models import AccountabilityReport

        context = super().get_context_data(**kwargs)
        context['title'] = 'Rendición de cuenta'
        context['parent'] = 'institucion'
        context['segment'] = 'institution_accountability'
        context['company'] = CompanySettings.get_instance()
        context['reports'] = AccountabilityReport.objects.filter(is_published=True)
        return context


class ComplianceProcedureView(TemplateView):
    template_name = 'pages/home/institution/compliance_procedure.html'
    procedure_type = None
    segment = ''

    HERO_DESCRIPTIONS = {
        'incident_response': (
            'Información sobre el procedimiento de notificación y gestión de incidentes de '
            'ciberseguridad que afecten datos personales, conforme a la Resolución 58/2022.'
        ),
        'backup_restore': (
            'Información sobre el respaldo y la restauración de bases de datos con datos '
            'personales, conforme a la Resolución 58/2022.'
        ),
    }

    def get_context_data(self, **kwargs):
        from apps.core.models import ComplianceProcedure

        context = super().get_context_data(**kwargs)
        procedure = ComplianceProcedure.objects.filter(
            procedure_type=self.procedure_type, is_published=True
        ).first()
        context['procedure'] = procedure
        context['title'] = (
            procedure.title
            if procedure
            else dict(ComplianceProcedure.ProcedureType.choices).get(self.procedure_type, '')
        )
        context['hero_description'] = self.HERO_DESCRIPTIONS.get(self.procedure_type, '')
        context['parent'] = 'institucion'
        context['segment'] = self.segment
        context['company'] = CompanySettings.get_instance()
        return context


class PublicInformationRequestView(FormView):
    template_name = 'pages/home/institution/public_information_request.html'
    form_class = PublicInformationRequestForm
    success_url = '.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Solicitud de información pública'
        context['parent'] = 'institucion'
        context['segment'] = 'public_information_request'
        context['company'] = CompanySettings.get_instance()
        return context

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            'Su solicitud ha sido recibida correctamente. '
            'Le responderemos en un plazo de hasta quince días hábiles '
            'desde su recepción, conforme a la Ley 168/2024.',
        )
        return super().form_valid(form)


class SecurityIncidentProcedureView(ComplianceProcedureView):
    procedure_type = 'incident_response'
    segment = 'institution_incident_response'


class DataBackupProcedureView(ComplianceProcedureView):
    procedure_type = 'backup_restore'
    segment = 'institution_backup_restore'
