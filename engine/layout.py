"""Layout dispatcher — routes rendering to the selected template.

Provides a backward-compatible `render()` function and new `render_html()`
that delegate to the template registry in engine/templates/.
"""

from engine.templates import get_template, DEFAULT_TEMPLATE


def render(content: dict, output_path: str, template_name: str = None) -> str:
    """Render content dict to PDF using the named template."""
    tmpl = get_template(template_name or DEFAULT_TEMPLATE)
    return tmpl.render_pdf(content, output_path)


def render_html(content: dict, output_path: str, template_name: str = None) -> str:
    """Render content dict to HTML using the named template."""
    tmpl = get_template(template_name or DEFAULT_TEMPLATE)
    return tmpl.render_html(content, output_path)
