import os
from pathlib import Path
from typing import Dict, List

WORKFLOWS_DIR = Path(os.getenv("WORKFLOW_DEFINITIONS_PATH", "workflow_definitions"))


def list_templates() -> List[Dict[str, str]]:
    templates: List[Dict[str, str]] = []
    for wirl in WORKFLOWS_DIR.glob("**/*.wirl"):
        templates.append({"id": wirl.stem, "name": wirl.stem, "path": str(wirl)})
    return templates


def get_template(identifier: str | None) -> Dict[str, str] | None:
    if not identifier:
        return None
    for tpl in list_templates():
        if tpl["id"] == identifier or tpl["name"] == identifier:
            return tpl
    return None
