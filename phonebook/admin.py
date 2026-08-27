import os

from django.contrib import admin
from django.db.models import Count, Max
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timesince import timesince
from django.utils import timezone

from .models import PhonebookXML, PhonebookAccessLog
from sipbook import settings

# A small, cohesive color set used across badges so manufacturers/models
# get a stable, distinct color per name rather than random ones each reload.
_PALETTE = [
    ("#7c3aed", "#ede9fe"),  # violet
    ("#0ea5e9", "#e0f2fe"),  # sky
    ("#10b981", "#d1fae5"),  # emerald
    ("#f59e0b", "#fef3c7"),  # amber
    ("#ef4444", "#fee2e2"),  # red
    ("#ec4899", "#fce7f3"),  # pink
    ("#6366f1", "#e0e7ff"),  # indigo
]


def _color_for(value: str):
    idx = sum(ord(c) for c in value) % len(_PALETTE)
    return _PALETTE[idx]


@admin.register(PhonebookXML)
class PhonebookXMLAdmin(admin.ModelAdmin):
    list_display = (
        "manufacturer_badge",
        "model_badge",
        "xml_filename_display",
        "phonebook_url_display",
        "hit_count_display",
        "freshness_display",
    )

    list_filter = ("manufacturer", "model")
    search_fields = ("manufacturer", "model", "token")
    ordering = ("-updated_at",)
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _hit_count=Count("access_logs"),
            _last_hit=Max("access_logs__accessed_at"),
        )

    readonly_fields = (
        "token_display",
        "phonebook_url_display",
        "meta_display",
    )

    fieldsets = (
        ("Device", {
            "fields": ("manufacturer", "model", "xml_file"),
            "description": "The manufacturer and model determine the URL path "
                           "this phonebook is served under.",
        }),
        ("Access", {
            "fields": ("token_display", "phonebook_url_display"),
        }),
        ("File info", {
            "fields": ("meta_display",),
            "classes": ("collapse",),
        }),
    )

    class Media:
        css = {"all": ("phonebook/admin_extra.css",)}

    # ------------------------------------------------------------------
    # List display
    # ------------------------------------------------------------------

    @admin.display(description="Manufacturer", ordering="manufacturer")
    def manufacturer_badge(self, obj):
        fg, bg = _color_for(obj.manufacturer)
        return format_html(
            '<span class="pb-badge" style="color:{};background:{};">'
            '<span class="pb-dot" style="background:{};"></span>{}</span>',
            fg, bg, fg, obj.manufacturer,
        )

    @admin.display(description="Model", ordering="model")
    def model_badge(self, obj):
        return format_html(
            '<span class="pb-badge pb-badge--muted">{}</span>', obj.model,
        )

    @admin.display(description="Xml file")
    def xml_filename_display(self, obj):
        if not obj.xml_file:
            return format_html('<span class="pb-empty">{}</span>', "No file")

        filename = os.path.basename(obj.xml_file.name)
        size_str = self._safe_size(obj)
        mtime_str = self._safe_mtime(obj)
        meta_line = " · ".join(p for p in (size_str, mtime_str) if p) or "—"

        return format_html(
            """
            <a href="{}" target="_blank" class="pb-file" title="{}">
                <span class="pb-file-icon">📄</span>
                <span class="pb-file-text">
                    <span class="pb-file-name">{}</span>
                    <span class="pb-file-meta">{}</span>
                </span>
            </a>
            """,
            obj.xml_file.url, obj.xml_file.name, filename, meta_line,
        )

    @admin.display(description="Phonebook link")
    def phonebook_url_display(self, obj):
        if not obj or not obj.pk:
            return "-"

        path = reverse(
            "phonebook:phonebook_xml",
            kwargs={"manufacturer": obj.manufacturer, "token": obj.token},
        )
        url = f"{settings.PHONEBOOK_BASE_URL}{path}"

        return format_html(
            """
            <div class="pb-actions">
                <button type="button" class="pb-btn pb-btn--ghost"
                    onclick="pbCopy_{0}('{1}', this)">
                    <span class="pb-btn-icon">⧉</span>
                    <span class="pb-btn-label">Copy URL</span>
                </button>
                <a href="{1}" target="_blank" class="pb-btn pb-btn--accent">
                    <span class="pb-btn-icon">↗</span>
                    <span class="pb-btn-label">Open</span>
                </a>
            </div>
            <script>
            function pbCopy_{0}(url, btn) {{
                navigator.clipboard.writeText(url).then(function() {{
                    const label = btn.querySelector('.pb-btn-label');
                    const original = label.textContent;
                    label.textContent = 'Copied!';
                    btn.classList.add('pb-btn--success');
                    setTimeout(function() {{
                        label.textContent = original;
                        btn.classList.remove('pb-btn--success');
                    }}, 1400);
                }}).catch(function() {{
                    const ta = document.createElement('textarea');
                    ta.value = url;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    ta.remove();
                }});
            }}
            </script>
            """,
            obj.pk, url,
        )

    @admin.display(description="Devices polling", ordering="_hit_count")
    def hit_count_display(self, obj):
        count = getattr(obj, "_hit_count", 0) or 0
        last_hit = getattr(obj, "_last_hit", None)

        if count == 0:
            return format_html(
                '<span class="pb-hit pb-hit--zero">'
                '<span class="pb-hit-dot"></span>{}</span>',
                "Never polled",
            )

        last_str = f"last {timesince(last_hit)} ago" if last_hit else ""
        log_url = (
                reverse("admin:phonebook_phonebookaccesslog_changelist")
                + f"?phonebook__id__exact={obj.pk}"
        )
        return format_html(
            '<a href="{}" class="pb-hit"><span class="pb-hit-dot"></span>'
            '<span class="pb-hit-count">{}</span> hit{} '
            '<span class="pb-hit-sub">{}</span></a>',
            log_url, count, "" if count == 1 else "s", last_str,
        )

    @admin.display(description="Updated")
    def freshness_display(self, obj):
        if not obj.updated_at:
            return "-"
        age = timezone.now() - obj.updated_at
        if age.total_seconds() < 3600:
            dot = "#10b981"  # green — fresh
        elif age.total_seconds() < 86400 * 7:
            dot = "#f59e0b"  # amber — this week
        else:
            dot = "#94a3b8"  # gray — stale
        return format_html(
            '<span class="pb-time"><span class="pb-time-dot" '
            'style="background:{};"></span>{} ago</span>',
            dot, timesince(obj.updated_at),
        )

    # ------------------------------------------------------------------
    # Detail view
    # ------------------------------------------------------------------

    @admin.display(description="Token")
    def token_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        short = f"{obj.token[:8]}···{obj.token[-6:]}"
        return format_html(
            """
            <div class="pb-token">
                <code class="pb-token-code">{}</code>
                <button type="button" class="pb-btn pb-btn--ghost pb-btn--sm"
                    onclick="pbCopyToken_{}('{}', this)">
                    <span class="pb-btn-icon">⧉</span>
                    <span class="pb-btn-label">Copy full token</span>
                </button>
            </div>
            <script>
            function pbCopyToken_{1}(token, btn) {{
                navigator.clipboard.writeText(token).then(function() {{
                    const label = btn.querySelector('.pb-btn-label');
                    label.textContent = 'Copied!';
                    setTimeout(function() {{ label.textContent = 'Copy full token'; }}, 1400);
                }});
            }}
            </script>
            """,
            short, obj.pk, obj.token,
        )

    @admin.display(description="File details")
    def meta_display(self, obj):
        if not obj or not obj.xml_file:
            return "-"
        size_str = self._safe_size(obj) or "unknown"
        mtime_str = self._safe_mtime(obj) or "unknown"
        return format_html(
            '<div class="pb-meta-grid">'
            '<div><span class="pb-meta-label">Path</span>{}</div>'
            '<div><span class="pb-meta-label">Size</span>{}</div>'
            '<div><span class="pb-meta-label">Modified</span>{}</div>'
            '</div>',
            obj.xml_file.name, size_str, mtime_str,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_size(self, obj):
        try:
            return self._humanize_bytes(obj.xml_file.size)
        except (OSError, NotImplementedError, ValueError):
            return None

    def _safe_mtime(self, obj):
        try:
            mtime = obj.xml_file.storage.get_modified_time(obj.xml_file.name)
            if timezone.is_naive(mtime):
                mtime = timezone.make_aware(mtime, timezone.get_default_timezone())
            return f"{timesince(mtime)} ago"
        except (OSError, NotImplementedError, ValueError):
            return None

    @staticmethod
    def _humanize_bytes(num_bytes):
        size = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024


@admin.register(PhonebookAccessLog)
class PhonebookAccessLogAdmin(admin.ModelAdmin):
    """Read-only browse view of every device fetch. Logs are created by the
    phonebook view itself, never manually — so add/change are disabled."""

    list_display = (
        "phonebook",
        "ip_address",
        "user_agent_short",
        "accessed_at",
    )
    list_filter = ("phonebook__manufacturer", "phonebook__model", "accessed_at")
    search_fields = ("ip_address", "user_agent", "phonebook__manufacturer", "phonebook__model")
    date_hierarchy = "accessed_at"
    ordering = ("-accessed_at",)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="User agent")
    def user_agent_short(self, obj):
        ua = obj.user_agent or "—"
        return ua if len(ua) <= 60 else ua[:57] + "…"
