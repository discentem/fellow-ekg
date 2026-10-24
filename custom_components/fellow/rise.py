"""Rapid temperature-rise detection for the Stagg EKG.

The kettle has no water-level sensor, but the rate at which the water
temperature climbs while heating is a good proxy for how much water is in
it: the same heater warms a small mass of water (or just the empty steel
body) much faster than a full kettle.

Measured on a Stagg EKG Pro (firmware 1.1.75SSP, 5 s averages):

    nearly full (~0.9 L)   ~0.44 C/s average, ~0.6 C/s peak
    low fill   (~0.2 L)    ~1.25 C/s average, ~1.65 C/s peak

In both runs the reading stayed flat for the first ~20 s after the heat
cycle started (element/sensor lag), so the detector ignores that window.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Deque, Optional, Tuple

DEFAULT_RISE_THRESHOLD = 3.0  # C/s - roughly 1.8x the fastest low-fill rate seen
DEFAULT_WINDOW_SECONDS = 10.0
MIN_SPAN_SECONDS = 4.0
STARTUP_GRACE_SECONDS = 20.0


class RapidRiseDetector:
    """Track temperature during a heat cycle and flag implausibly fast rises.

    Latches `triggered` until reset(): normally a new heat cycle or a lift.
    """

    def __init__(self, threshold=DEFAULT_RISE_THRESHOLD,
                 window=DEFAULT_WINDOW_SECONDS, grace=STARTUP_GRACE_SECONDS):
        self.threshold = threshold
        self.window = window
        self.grace = grace
        self._samples: Deque[Tuple[float, float]] = deque()
        self._heat_started_at: Optional[float] = None
        self.rate: Optional[float] = None
        self.triggered = False
        self.triggered_rate: Optional[float] = None

    def reset(self) -> None:
        self._samples.clear()
        self._heat_started_at = None
        self.rate = None
        self.triggered = False
        self.triggered_rate = None

    def update(self, now: float, temp_c: Optional[float], heating: bool) -> bool:
        """Record a sample. Returns True only on the poll that first triggers."""
        if not heating:
            self._samples.clear()
            self._heat_started_at = None
            self.rate = None
            return False
        if self._heat_started_at is None:
            self.reset()
            self._heat_started_at = now
        if temp_c is None or math.isnan(temp_c):
            self._samples.clear()
            self.rate = None
            return False
        self._samples.append((now, temp_c))
        while self._samples and now - self._samples[0][0] > self.window:
            self._samples.popleft()
        first_t, first_temp = self._samples[0]
        span = now - first_t
        if span < MIN_SPAN_SECONDS:
            self.rate = None
            return False
        self.rate = (temp_c - first_temp) / span
        if (not self.triggered and now - self._heat_started_at >= self.grace
                and self.rate > self.threshold):
            self.triggered = True
            self.triggered_rate = self.rate
            return True
        return False


# Auto-stop retries. One stop command is not enough: the kettle sometimes
# ignores `ss S_Off` during a state change, or stops answering HTTP for a
# few seconds. The coordinator polls every 5 s anyway, so it retries from
# the polls until one shows the kettle off, then gives up loudly.
DEFAULT_STOP_GIVE_UP_SECONDS = 60.0
DEFAULT_STOP_MAX_ATTEMPTS = 10

STOP_PENDING = "pending"
STOP_STOPPED = "stopped"
STOP_FAILED = "failed"

ACTION_SEND = "send"
ACTION_GIVE_UP = "give_up"


class AutoStopTracker:
    """Decide on each poll whether to send another stop, or give up.

    `status` is None (no auto-stop running), STOP_PENDING, STOP_STOPPED or
    STOP_FAILED. STOP_STOPPED and STOP_FAILED stay put until reset().
    """

    def __init__(self, give_up_after=DEFAULT_STOP_GIVE_UP_SECONDS,
                 max_attempts=DEFAULT_STOP_MAX_ATTEMPTS):
        self.give_up_after = give_up_after
        self.max_attempts = max_attempts
        self.status: Optional[str] = None
        self.attempts = 0
        self._started_at: Optional[float] = None

    def reset(self) -> None:
        self.status = None
        self.attempts = 0
        self._started_at = None

    def start(self, now: float) -> None:
        self.status = STOP_PENDING
        self.attempts = 0
        self._started_at = now

    def poll(self, now: float, running: bool, in_flight: bool) -> Optional[str]:
        """Record a poll. Returns ACTION_SEND, ACTION_GIVE_UP or None.

        `running` is whether the kettle is still heating or holding;
        `in_flight` is whether a previous stop attempt is still running.
        """
        if self.status != STOP_PENDING:
            return None
        if not running:
            self.status = STOP_STOPPED
            return None
        if in_flight:
            return None
        if (self.attempts >= self.max_attempts
                or now - self._started_at >= self.give_up_after):
            self.status = STOP_FAILED
            return ACTION_GIVE_UP
        self.attempts += 1
        return ACTION_SEND
