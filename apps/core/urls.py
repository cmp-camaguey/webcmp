from django.urls import path

from apps.core.views import (
    ActivityLogListView,
    CompanySettingsAjaxUpdateView,
    CompanySettingsUpdateView,
    CookieConsentView,
    DataSubjectRequestListView,
    DataSubjectRequestUpdateView,
    EmailRecipientListCreateView,
    EmailRecipientListDeleteView,
    EmailRecipientListListView,
    EmailRecipientListUpdateView,
    EnvironmentApplyStatusView,
    EnvironmentConfigApplyView,
    EnvironmentConfigView,
    EnvironmentMaintenanceDisableView,
    PublicInformationRequestListView,
    PublicInformationRequestUpdateView,
    SiteConfigurationUpdateView,
    TermsChangeNoticeCreateView,
    TermsChangeNoticeDeleteView,
    TermsChangeNoticeListView,
    TermsChangeNoticeUpdateView,
)

app_name = 'core'

urlpatterns = [
    path('empresa/', CompanySettingsUpdateView.as_view(), name='company_settings'),
    path('empresa/ajax/', CompanySettingsAjaxUpdateView.as_view(), name='company_settings_ajax'),
    path('configuracion-sitio/', SiteConfigurationUpdateView.as_view(), name='site_configuration'),
    path('entorno/', EnvironmentConfigView.as_view(), name='environment_config'),
    path(
        'entorno/aplicar/',
        EnvironmentConfigApplyView.as_view(),
        name='environment_apply',
    ),
    path(
        'entorno/aplicar/estado/',
        EnvironmentApplyStatusView.as_view(),
        name='environment_apply_status',
    ),
    path(
        'entorno/mantenimiento/desactivar/',
        EnvironmentMaintenanceDisableView.as_view(),
        name='environment_maintenance_disable',
    ),
    path('listas-correo/', EmailRecipientListListView.as_view(), name='email_recipient_list'),
    path(
        'listas-correo/crear/',
        EmailRecipientListCreateView.as_view(),
        name='email_recipient_create',
    ),
    path(
        'listas-correo/<uuid:pk>/editar/',
        EmailRecipientListUpdateView.as_view(),
        name='email_recipient_update',
    ),
    path(
        'listas-correo/<uuid:pk>/eliminar/',
        EmailRecipientListDeleteView.as_view(),
        name='email_recipient_delete',
    ),
    path('auditoria/', ActivityLogListView.as_view(), name='activity_log'),
    path(
        'solicitudes-derechos/',
        DataSubjectRequestListView.as_view(),
        name='data_subject_request_list',
    ),
    path(
        'solicitudes-derechos/<int:pk>/editar/',
        DataSubjectRequestUpdateView.as_view(),
        name='data_subject_request_update',
    ),
    path(
        'solicitudes-informacion-publica/',
        PublicInformationRequestListView.as_view(),
        name='public_information_request_list',
    ),
    path(
        'solicitudes-informacion-publica/<int:pk>/editar/',
        PublicInformationRequestUpdateView.as_view(),
        name='public_information_request_update',
    ),
    path(
        'avisos-cambios-legales/',
        TermsChangeNoticeListView.as_view(),
        name='terms_change_notice_list',
    ),
    path(
        'avisos-cambios-legales/crear/',
        TermsChangeNoticeCreateView.as_view(),
        name='terms_change_notice_create',
    ),
    path(
        'avisos-cambios-legales/<uuid:pk>/editar/',
        TermsChangeNoticeUpdateView.as_view(),
        name='terms_change_notice_update',
    ),
    path(
        'avisos-cambios-legales/<uuid:pk>/eliminar/',
        TermsChangeNoticeDeleteView.as_view(),
        name='terms_change_notice_delete',
    ),
    path('cookies/consentimiento/', CookieConsentView.as_view(), name='cookie_consent'),
]
