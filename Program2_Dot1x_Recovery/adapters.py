"""Conservative OFFLINE CLI inspection; no live command transport.

These parsers are fixture-tested, not device/firmware-certified adapters.
Unknown configuration is retained verbatim; ambiguous port policy is rejected.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PortConfig:
    vendor: str
    interface: str
    lines: tuple[str, ...]
    data_vlan: int | None
    voice_vlan: int | None
    dynamic: bool


def inspect_config(vendor, interface, text):
    lines = tuple(line.strip() for line in text.splitlines() if line.strip() and line.strip() != "!")
    if not lines or lines[0].casefold() != ("interface " + interface).casefold():
        raise ValueError("Interface identity mismatch")
    if any(re.search(r"trunk|channel-group|eth-trunk|ip address|management", line, re.I) for line in lines):
        raise ValueError("Excluded uplink, aggregate or management configuration")
    if vendor == "cisco":
        if "switchport mode access" not in lines:
            raise ValueError("Explicit access mode required")
        data = [
            int(m.group(1)) for line in lines if (m := re.fullmatch(r"switchport access vlan (\d+)", line))
        ]
        voice = [
            int(m.group(1)) for line in lines if (m := re.fullmatch(r"switchport voice vlan (\d+)", line))
        ]
        dynamic = any(
            re.search(r"authentication port-control auto|dot1x pae authenticator|mab", line) for line in lines
        )
    elif vendor == "huawei":
        if "port link-type hybrid" not in lines:
            raise ValueError("Explicit hybrid mode required")
        data = [
            int(m.group(1)) for line in lines if (m := re.fullmatch(r"port hybrid pvid vlan (\d+)", line))
        ]
        voice = [int(m.group(1)) for line in lines if (m := re.fullmatch(r"voice-vlan (\d+) enable", line))]
        dynamic = any(line.startswith("authentication-profile ") for line in lines)
        # Complex membership needs actual firmware/template validation, not inference.
        if any(
            "port hybrid untagged vlan" in line and not re.fullmatch(r"port hybrid untagged vlan \d+", line)
            for line in lines
        ):
            raise ValueError("Ambiguous hybrid VLAN membership")
    else:
        raise ValueError("Unsupported vendor")
    if len(data) > 1 or len(voice) > 1:
        raise ValueError("Ambiguous VLAN configuration")
    return PortConfig(
        vendor, interface, lines, data[0] if data else None, voice[0] if voice else None, dynamic
    )


def require_live_adapter(*args, **kwargs):
    raise NotImplementedError("No firmware-certified live recovery adapter is installed; no commands sent")
