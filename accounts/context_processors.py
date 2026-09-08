from django.conf import settings
from .models import User


def demo_personas(request):
    """Provides demo personas for the one-click role switcher bar when demo mode is active."""
    enable_demo = getattr(settings, 'ENABLE_DEMO_MODE', False)
    if not enable_demo:
        return {
            'demo_users': [],
            'current_user': request.user,
            'enable_demo_mode': False,
        }

    demo_users = User.objects.filter(username__in=['alice', 'bob', 'charlie', 'sarah', 'admin']).order_by('id')

    return {
        'demo_users': demo_users,
        'current_user': request.user,
        'enable_demo_mode': True,
    }

