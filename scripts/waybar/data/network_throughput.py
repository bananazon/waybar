from dataclasses import dataclass


@dataclass
class Sample:
    interface: str | None = None
    r_bytes: int = 0
    r_packets: int = 0
    r_errs: int = 0
    r_drop: int = 0
    r_fifo: int = 0
    r_frame: int = 0
    r_compressed: int = 0
    r_multicast: int = 0
    t_bytes: int = 0
    t_packets: int = 0
    t_errs: int = 0
    t_drop: int = 0
    t_fifo: int = 0
    t_colls: int = 0
    t_carrier: int = 0
    t_compressed: int = 0


@dataclass
class NetworkThroughput:
    success: bool = False
    error: str | None = None
    alias: str | None = None
    device_name: str | None = None
    driver: str | None = None
    icon: str | None = None
    interface: str = ""
    ip_private: str | None = None
    ip_public: str | None = None
    mac_address: str | None = None
    model: str | None = None
    received: str | None = None
    transmitted: str | None = None
    vendor: str | None = None
    updated: str | None = None
