"""VerifiedHands — the execute -> wait -> re-poll -> confirm wrapper.

Every WRITE action goes through this so the brain never trusts a click; it
trusts an observed post-condition. If the post-condition can't be confirmed
within the timeout, ``ActionResult.confirmed`` stays False and the message
explains why.

Created fresh in Phase 5 (no pre-existing VerifiedHands was present in the repo).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .adapters.base import ActionResult


class VerifiedHands:
    def __init__(
        self,
        settle_seconds: float = 6.0,
        poll_interval: float = 4.0,
        timeout_seconds: float = 45.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        # settle: give the device time to actually act before first poll
        self.settle_seconds = settle_seconds
        self.poll_interval = poll_interval
        self.timeout_seconds = timeout_seconds
        self._sleep = sleep

    def do(
        self,
        *,
        action: str,
        target: str,
        execute: Callable[[], Any],
        poll: Callable[[], Any],
        confirm: Callable[[Any], bool],
        before: Optional[Callable[[], Any]] = None,
    ) -> ActionResult:
        """Run a verified write.

        - ``before()``  (optional): snapshot state before acting.
        - ``execute()`` : perform the write (click the button, etc.).
        - ``poll()``    : read current state (called repeatedly).
        - ``confirm(state)`` : True when the post-condition holds.
        """
        result = ActionResult(action=action, target=target)

        # snapshot "before"
        if before is not None:
            try:
                result.before = before()
            except Exception as e:  # snapshot failure is non-fatal
                result.before = f"<before-snapshot-failed: {e}>"

        # execute
        try:
            execute()
            result.ok = True
        except Exception as e:
            result.ok = False
            result.message = f"execute failed: {e}"
            return result

        # let the device settle before the first poll
        self._sleep(self.settle_seconds)

        # re-poll until confirmed or timed out
        deadline = self.settle_seconds + self.timeout_seconds
        elapsed = self.settle_seconds
        last_state: Any = None
        while True:
            result.attempts += 1
            try:
                last_state = poll()
                result.after = last_state
                if confirm(last_state):
                    result.confirmed = True
                    result.message = f"confirmed after {result.attempts} poll(s)"
                    return result
            except Exception as e:
                result.message = f"poll error (attempt {result.attempts}): {e}"

            if elapsed >= deadline:
                if not result.message:
                    result.message = (
                        f"executed but post-condition not confirmed within "
                        f"{self.timeout_seconds:.0f}s ({result.attempts} polls)"
                    )
                result.after = last_state
                return result

            self._sleep(self.poll_interval)
            elapsed += self.poll_interval
