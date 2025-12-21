from dataclasses import dataclass, field


@dataclass
class Server:
    cc: str | None = None
    city: str | None = None
    country: str | None = None
    d: str | None = None
    host: str | None = None
    id: str | int | None = None
    ip: str | None = None
    lat: str | None = None
    latency: float = 0.0
    lon: str | None = None
    name: str = ""
    region: str | None = None
    sponsor: str | None = None
    timezone: str | None = None
    url: str | None = None


@dataclass
class Client:
    city: str | None = None
    country: str | None = None
    ip: str | None = None
    isp: str | None = None
    ispdlavg: str | int | None = None
    isprating: str | float | None = None
    ispulavg: str | int | None = None
    lat: str | None = None
    loggedin: str | bool | None = None
    lon: str | None = None
    rating: str | int | None = None
    region: str | None = None
    timezone: str | None = None


@dataclass
class Results:
    success: bool = False
    error: str | None = None
    icon: str = ""
    bytes_received: float = 0.0
    bytes_sent: float = 0.0
    client: Client = field(default_factory=Client)
    download: float = 0.0
    ping: float = 0.0
    server: Server = field(default_factory=Server)
    share: str | None = None
    speed_rx: float = 0.0
    speed_tx: float = 0.0
    timestamp: str = ""
    updated: str | None = None
    upload: float = 0.0
