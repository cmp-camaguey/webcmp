from django.views.generic import TemplateView

from apps.core.models import CompanySettings


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


class LegalNoticeView(TemplateView):
    template_name = 'pages/home/institution/legal_notice.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Aviso legal'
        context['parent'] = 'institucion'
        context['segment'] = 'legal_notice'
        context['company'] = CompanySettings.get_instance()
        return context
