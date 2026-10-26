"""Deterministic simulated console/jump state machine.

No serial bytes are sent. Live gateway recovery requires a firmware adapter.
"""

import threading
from contextlib import contextmanager


class LostGatewayContext(RuntimeError):
    pass


class SimulatedJump:
    def __init__(self, gateway="SIM-GATEWAY"):
        self.gateway = gateway
        self.prompt = gateway + "#"
        self.owner = threading.Lock()
        self.trusted = set()
        self.healthy = True

    def enroll_simulated_target(self, hostname):
        # Synthetic trust fixtures only. This is never real SSH enrollment.
        self.trusted.add(hostname.casefold())

    def verify_gateway(self):
        if not self.healthy or self.prompt != self.gateway + "#":
            self.healthy = False
            raise LostGatewayContext("Gateway identity could not be recovered; stop batch")

    @contextmanager
    def target(self, hostname):
        with self.owner:
            self.verify_gateway()
            if hostname.casefold() not in self.trusted:
                raise ValueError("Target trust is distinct from gateway trust")
            self.prompt = hostname + "#"
            try:
                yield self
            finally:
                if self.healthy:
                    self.prompt = self.gateway + "#"
                self.verify_gateway()
