from django.urls import path

from apps.core.views import (
    ActivityLogListView,
    CompanySettingsAjaxUpdateView,
    CompanySettingsUpdateView,
    EmailRecipientListCreateView,
    EmailRecipientListDeleteView,
    EmailRecipientListListView,
    EmailRecipientListUpdateView,
    EnvironmentApplyStatusView,
    EnvironmentConfigApplyView,
    EnvironmentConfigView,
    EnvironmentMaintenanceDisableView,
    SiteConfigurationUpdateView,
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
]
