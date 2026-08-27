import secrets

from django.db import models

# Create your models here.

class PhonebookXML(models.Model):
    manufacturer = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    token = models.CharField(max_length=64, unique=True, editable=False, default=secrets.token_urlsafe)
    xml_file = models.FileField(upload_to='phonebooks/')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('manufacturer', 'model')
        ordering = ['manufacturer', 'model']

    def __str__(self):
        return f"{self.manufacturer}/{self.model}"

    @property
    def phonebook_url(self):
        return f"/p/{self.manufacturer}/{self.token}.xml"


class PhonebookAccessLog(models.Model):
    """One row per successful phonebook XML fetch by a device."""

    phonebook = models.ForeignKey(
        PhonebookXML,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=512, blank=True, default="")
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-accessed_at",)
        indexes = [
            models.Index(fields=["phonebook", "-accessed_at"]),
        ]

    def __str__(self):
        return f"{self.phonebook} — {self.ip_address} @ {self.accessed_at:%Y-%m-%d %H:%M}"