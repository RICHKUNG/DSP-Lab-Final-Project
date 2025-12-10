"""Shared helpers for locating command templates in tests."""

import os

ENV_VAR_NAME = "CMD_TEMPLATES_DIR"


def _resolve_dir(path: str):
    """Return an absolute version of path if it exists."""
    expanded = os.path.abspath(os.path.expanduser(path))
    return expanded if os.path.isdir(expanded) else None


def locate_cmd_templates():
    """
    Return the path to command templates, preferring tests/cmd_templates and
    falling back to project-level cmd_templates. An environment variable
    CMD_TEMPLATES_DIR can override the default lookup.
    """
    env_override = os.environ.get(ENV_VAR_NAME)
    if env_override:
        resolved = _resolve_dir(env_override)
        if resolved:
            return resolved
        raise FileNotFoundError(
            f"{ENV_VAR_NAME} is set to '{env_override}' but that directory does not exist."
        )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    tests_templates = _resolve_dir(os.path.join(current_dir, "cmd_templates"))
    if tests_templates:
        return tests_templates

    project_root = os.path.dirname(current_dir)
    project_templates = _resolve_dir(os.path.join(project_root, "cmd_templates"))
    if project_templates:
        return project_templates

    raise FileNotFoundError(
        "Could not locate cmd_templates. Checked "
        f"'{os.path.join(current_dir, 'cmd_templates')}' and "
        f"'{os.path.join(project_root, 'cmd_templates')}'. "
        "Set CMD_TEMPLATES_DIR to the correct directory."
    )
