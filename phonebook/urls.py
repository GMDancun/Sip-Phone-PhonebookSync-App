from django.urls import path
from . import views

app_name = 'phonebook'

urlpatterns = [
    # Example: /p/fanvil/x303p.xml
    path(
        "p/<str:manufacturer>/<str:token>.xml", views.phonebook_xml, name="phonebook_xml",
    )
]
