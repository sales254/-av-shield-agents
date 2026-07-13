"""AV Shield device-control layer (Phase 5+).

Provider-agnostic network adapters used by the brain to read status and drive
verified actions on physical gear. Phase 5 ships the Reyee/Ruijie Cloud adapter.
"""

from .verified_hands import VerifiedHands
from . import registry

__all__ = ["VerifiedHands", "registry"]
