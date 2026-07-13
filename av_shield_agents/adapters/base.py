"""Base network-adapter interface for the AV Shield device-control layer.

The "brain" (orchestration/decision layer) talks to physical network gear only
through this interface. Concrete adapters (Reyee, and later others) implement it.
Every WRITE action is expected to be driven through ``VerifiedHands`` so that the
brain always gets a confirmed before/after result rather than a fire-and-forget.

NOTE: This module was created fresh in Phase 5. The Phase 5 brief referred to an
"existing adapters/base.py" interface, but no such module existed in this repo,
so it is defined here. It is intentionally small and provider-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class DeviceType(str, Enum):
    SWITCH = "switch"
    AP = "ap"
    WIRELESS_BRIDGE = "wireless_bridge"
    CAMERA = "camera"
    UNKNOWN = "unknown"


class LinkState(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class OnlineState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #
@dataclass
class Device:
    """A device row as shown in the portal's Devices list."""
    sn: str                                   # serial number (the stable id)
    name: str = ""
    device_type: DeviceType = DeviceType.UNKNOWN
    status: OnlineState = OnlineState.UNKNOWN  # status dot: online/offline
    ip: str = ""
    mac: str = ""
    model: str = ""
    firmware: str = ""
    sync_state: str = ""
    raw: dict = field(default_factory=dict)   # any extra scraped fields

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class PortStatus:
    """A single switch port, from the port tile / hover tooltip."""
    port_id: str                              # e.g. "1" or "Port 1"
    status: LinkState = LinkState.UNKNOWN     # Up / Down
    speed: str = ""                           # Port Speed
    flow: str = ""                            # Flow
    rate: str = ""                            # Rate
    total_packets: str = ""                   # Total packets
    media_type: str = ""                      # Port media type
    poe_state: str = ""                       # Enabled / Disabled (PoE)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class CableDiagnostic:
    """Parsed result of a cable test on one port."""
    port: str
    cable_length_cm: Optional[int] = None
    diagnosis_result: str = ""                # raw "Diagnosis Result" text
    update_time: str = ""
    # Parsed booleans / health derived from diagnosis_result:
    cable_ok: bool = False
    short: bool = False
    break_detected: bool = False
    connector_health: str = "unknown"         # ok / degraded / bad / unknown
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class Alarm:
    """A row from the global alarms table (read-only)."""
    alarm_type: str = ""
    severity: str = ""
    group_project: str = ""                   # Group(project)
    alarm_source: str = ""
    device_sn: str = ""
    alias: str = ""
    generated_at: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass
class ActionResult:
    """Outcome of a WRITE action, produced by VerifiedHands."""
    action: str                               # e.g. "reboot_port"
    target: str                               # e.g. "G1T02L0000028:port3"
    ok: bool = False                          # executed without raising
    confirmed: bool = False                   # post-condition verified
    before: Any = None
    after: Any = None
    message: str = ""
    attempts: int = 0

    def to_dict(self) -> dict:
        return _clean(asdict(self))


def _clean(d: Any) -> Any:
    """Recursively convert enums to their values for JSON-friendly output."""
    if isinstance(d, dict):
        return {k: _clean(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_clean(v) for v in d]
    if isinstance(d, Enum):
        return d.value
    return d


# --------------------------------------------------------------------------- #
# Adapter interface
# --------------------------------------------------------------------------- #
class NetworkAdapter(ABC):
    """Interface every vendor adapter implements.

    ``site_id`` is a registry key (see ``av_shield_agents.registry``) that the
    adapter maps to a vendor-specific site/project. All methods are expected to
    be idempotent for reads; write methods carry an explicit ``confirm`` guard.
    """

    name: str = "base"

    # -- lifecycle -------------------------------------------------------- #
    @abstractmethod
    def close(self) -> None:
        """Release browser/session resources."""

    def __enter__(self) -> "NetworkAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- reads ------------------------------------------------------------ #
    @abstractmethod
    def list_devices(self, site_id: str, device_type: Optional[DeviceType] = None) -> list[Device]:
        """All devices at a site, optionally filtered by type."""

    def list_cameras(self, site_id: str) -> list[Device]:
        return self.list_devices(site_id, DeviceType.CAMERA)

    def list_switches(self, site_id: str) -> list[Device]:
        return self.list_devices(site_id, DeviceType.SWITCH)

    @abstractmethod
    def get_switch_status(self, site_id: str, switch_id: str) -> Optional[Device]:
        """Status for one switch (by SN or name)."""

    @abstractmethod
    def get_camera_status(self, site_id: str, camera_id: str) -> Optional[Device]:
        """Status for one camera (by SN or name)."""

    @abstractmethod
    def get_ports(self, site_id: str, switch_id: str) -> list[PortStatus]:
        """Port status list for a switch."""

    @abstractmethod
    def get_alarms(self, level: str = "NORMAL") -> list[Alarm]:
        """Read-only global alarms. Never auto-acts."""

    # -- writes (guarded) ------------------------------------------------- #
    @abstractmethod
    def reboot_port(self, site_id: str, switch_id: str, port: str, confirm: bool = False) -> ActionResult:
        """Bounce a single PoE port (execute -> wait -> re-poll -> confirm)."""

    @abstractmethod
    def run_cable_diagnostic(self, site_id: str, switch_id: str, port: str) -> CableDiagnostic:
        """Run a cable test on one port and return the parsed result."""

    @abstractmethod
    def reboot_switch(self, site_id: str, switch_id: str, confirm: bool = False) -> ActionResult:
        """Reboot an entire switch."""
