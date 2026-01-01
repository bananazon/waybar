from dataclasses import dataclass, field


@dataclass
class QuakeProperties:
    alert: str | None = None
    cdi: float | None = 0.0
    code: str | None = None
    detail: str | None = None
    dmin: float | None = 0.0
    felt: int = 0
    gap: int = 0
    ids: str | None = None
    mag: float | None = 0.0
    magType: str | None = None
    mmi: float | None = 0.0
    net: str | None = None
    nst: int = 0
    place: str | None = None
    rms: float | None = 0.0
    sig: int = 0
    sources: str | None = None
    status: str | None = None
    time: int = 0
    title: str | None = None
    tsunami: int = 0
    type: str | None = None
    types: str | None = None
    tz: str | None = None
    updated: int = 0
    url: str | None = None


@dataclass
class QuakeGeometry:
    type: str | None = None
    coordinates: list[float] = field(default_factory=list)


@dataclass
class Quake:
    geometry: QuakeGeometry = field(default_factory=QuakeGeometry)
    id: str | None = None
    properties: QuakeProperties = field(default_factory=QuakeProperties)
    type: str | None = None


@dataclass
class QuakeData:
    success: bool = False
    error: str | None = None
    quakes: list[Quake] = field(default_factory=list)
    updated: str | None = None
