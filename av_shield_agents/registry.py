"""site_id -> vendor project/site mapping.

The brain refers to sites by a stable ``site_id``. Each adapter maps that id to
whatever the vendor portal calls the site. For Reyee that is the "Project Name"
shown in the Projects table / top-left project dropdown.

Seeded with the one site we are cleared to test against (Laquinta). Add the
remaining 13 Reyee projects here as they are onboarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SiteMapping:
    site_id: str
    reyee_project: str                 # Reyee "Project Name"
    # Optional convenience metadata (not required for operation):
    primary_switch_sn: str = ""
    notes: str = ""
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Registry. site_id keys are lowercase-stable; values map to portal names.
# --------------------------------------------------------------------------- #
SITE_REGISTRY: dict[str, SiteMapping] = {
    "laquinta": SiteMapping(
        site_id="laquinta",
        reyee_project="Laquinta",
        primary_switch_sn="G1T02L0000028",   # N.E.PoleSwitch, ES206GS-P, 192.168.1.58
        notes="Phase 5 test site. Read-only until explicitly cleared for writes.",
    ),
    # TODO: add the other 13 Reyee projects:
    # "site_id": SiteMapping(site_id="...", reyee_project="<Project Name>"),
}


def resolve(site_id: str) -> SiteMapping:
    key = (site_id or "").strip().lower()
    if key not in SITE_REGISTRY:
        known = ", ".join(sorted(SITE_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown site_id {site_id!r}. Known site_ids: {known}")
    return SITE_REGISTRY[key]


def reyee_project_for(site_id: str) -> str:
    return resolve(site_id).reyee_project
