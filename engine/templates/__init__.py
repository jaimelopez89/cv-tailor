"""Template registry for CV Tailor."""

from engine.templates.ember import EmberTemplate
from engine.templates.meridian import MeridianTemplate
from engine.templates.slate import SlateTemplate
from engine.templates.verdant import VerdantTemplate
from engine.templates.folio import FolioTemplate

TEMPLATES = {
    "ember": EmberTemplate,
    "meridian": MeridianTemplate,
    "slate": SlateTemplate,
    "verdant": VerdantTemplate,
    "folio": FolioTemplate,
}

DEFAULT_TEMPLATE = "ember"


def get_template(name: str = None):
    """Get template class by name. Returns instance."""
    name = (name or DEFAULT_TEMPLATE).lower()
    cls = TEMPLATES.get(name)
    if not cls:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template '{name}'. Available: {available}")
    return cls()


def list_templates() -> list:
    """Return list of (name, description) tuples."""
    result = []
    for name, cls in TEMPLATES.items():
        desc = getattr(cls, "description", "")
        result.append((name, desc))
    return result
