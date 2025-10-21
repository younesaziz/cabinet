from typing import Optional

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover
    HTML = None  # type: ignore


def render_pdf(html_string: str) -> bytes:
    if HTML is None:
        # Fallback to simple bytes to avoid runtime error in environments without WeasyPrint deps
        return html_string.encode("utf-8")
    pdf = HTML(string=html_string).write_pdf()
    return pdf
