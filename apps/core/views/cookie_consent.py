from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.core.models import CookieConsent


@method_decorator(csrf_exempt, name='dispatch')
class CookieConsentView(View):
    """API pública para registrar consentimiento de cookies.

    No requiere autenticación ni CSRF (es una API pública de consentimiento).
    El CSRF se omite porque el visitante puede no tener sesión iniciada y el
    consentimiento debe poder registrarse en la primera visita.
    """

    def post(self, request, *args, **kwargs):
        import json

        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError, UnicodeDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON'},
                status=400,
            )

        choice = data.get('choice')
        analytics = data.get('analytics', False)
        functional = data.get('functional', False)

        valid_choices = ['accept_all', 'reject_analytics', 'custom']
        if choice not in valid_choices:
            return JsonResponse(
                {'success': False, 'error': 'Invalid choice'},
                status=400,
            )

        # Validaciones de coherencia
        if choice == 'accept_all' and not (analytics and functional):
            return JsonResponse(
                {'success': False, 'error': 'accept_all requires analytics and functional true'},
                status=400,
            )
        if choice == 'reject_analytics' and (analytics or functional):
            return JsonResponse(
                {
                    'success': False,
                    'error': ('reject_analytics requires analytics and functional false'),
                },
                status=400,
            )

        try:
            CookieConsent.record_consent(request, choice, analytics, functional)
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': str(e)},
                status=500,
            )

        return JsonResponse({'success': True})
