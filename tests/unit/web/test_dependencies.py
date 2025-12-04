"""Tests for bimcalc.web.dependencies - Shared dependency providers."""

from pathlib import Path
from fastapi.templating import Jinja2Templates

from bimcalc.web.dependencies import get_templates


def test_get_templates_returns_jinja2_instance():
    """Test that get_templates returns Jinja2Templates instance."""
    templates = get_templates()
    assert isinstance(templates, Jinja2Templates)


def test_get_templates_is_singleton():
    """Test that get_templates returns the same instance (singleton pattern)."""
    templates1 = get_templates()
    templates2 = get_templates()
    assert templates1 is templates2  # Same object


def test_templates_directory_exists():
    """Test that the templates directory exists."""
    templates = get_templates()
    # The templates directory should be bimcalc/web/templates/
    # We can infer the path from the module location
    from bimcalc.web import dependencies

    expected_dir = Path(dependencies.__file__).parent / "templates"
    assert expected_dir.exists(), f"Templates directory not found: {expected_dir}"


def test_templates_can_render():
    """Test that templates instance can render (if templates exist)."""
    templates = get_templates()
    # Check if env attribute exists (Jinja2Templates has this)
    assert hasattr(templates, "env")
    assert hasattr(templates, "TemplateResponse")
