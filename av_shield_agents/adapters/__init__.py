from .base import (
    NetworkAdapter,
    Device,
    DeviceType,
    PortStatus,
    CableDiagnostic,
    Alarm,
    ActionResult,
    LinkState,
    OnlineState,
)

__all__ = [
    "NetworkAdapter",
    "Device",
    "DeviceType",
    "PortStatus",
    "CableDiagnostic",
    "Alarm",
    "ActionResult",
    "LinkState",
    "OnlineState",
    "ReyeeAdapter",
]


def __getattr__(name):
    # Lazy import so `verified_hands -> adapters.base` doesn't pull in the
    # Playwright-dependent reyee module (and avoids a circular import).
    if name == "ReyeeAdapter":
        from .reyee import ReyeeAdapter
        return ReyeeAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
