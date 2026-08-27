from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import PhonebookXML, PhonebookAccessLog


def _client_ip(request):
    """Best-effort real client IP, accounting for a reverse proxy (nginx/etc)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def phonebook_xml(request, manufacturer, token):
    entry = get_object_or_404(
        PhonebookXML,
        manufacturer__iexact=manufacturer,
        token=token,
    )

    with entry.xml_file.open("rb") as f:
        content = f.read()

    # Log the hit. Wrapped so a logging failure never breaks the actual
    # phonebook response the device is waiting on.
    try:
        PhonebookAccessLog.objects.create(
            phonebook=entry,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        )
    except Exception:
        pass

    return HttpResponse(
        content,
        content_type="application/xml",
    )