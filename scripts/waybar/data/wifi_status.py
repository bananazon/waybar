from dataclasses import dataclass, field


@dataclass
class WifiStatus:
    success: bool = False
    error: str | None = None
    authenticated: bool = False
    authorized: bool = False
    bandwidth: int = 0
    channel: int = 0
    ciphers: list[str] = field(default_factory=list)
    connected_time: int = 0
    frequency: int = 0
    interface: str | None = None
    signal_strength: int = 0
    ssid_mac: str | None = None
    ssid_name: str | None = None
    updated: str | None = None
