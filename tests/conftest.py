"""Shared test fixtures and helpers."""

import pytest

from tests.template_utils import locate_cmd_templates


@pytest.fixture(scope="session")
def template_dir():
    """Return path to templates, preferring tests/cmd_templates then project-level cmd_templates."""
    return locate_cmd_templates()
