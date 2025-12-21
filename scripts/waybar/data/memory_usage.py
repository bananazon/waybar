from dataclasses import dataclass, field


@dataclass
class DimmValues:
    array_handle: str | None = None
    asset_tag: str | None = None
    bank_locator: str | None = None
    cache_size: str | None = None
    configured_memory_speed: str | None = None
    configured_voltage: str | None = None
    data_width: str | None = None
    error_information_handle: str | None = None
    firmware_version: str | None = None
    form_factor: str | None = None
    locator: str | None = None
    logical_size: str | None = None
    manufacturer: str | None = None
    maximum_voltage: str | None = None
    memory_operating_mode_capability: str | None = None
    memory_subsystem_controller_manufacturer_id: str | None = None
    memory_subsystem_controller_product_id: str | None = None
    memory_technology: str | None = None
    minimum_voltage: str | None = None
    module_manufacturer_id: str | None = None
    module_product_id: str | None = None
    non_volatile_size: str | None = None
    part_number: str | None = None
    rank: str | None = None
    serial_number: str | None = None
    set: str | None = None
    size: str = ""
    size_raw: int = 0
    speed: str | None = None
    total_width: str | None = None
    type: str | None = None
    type_detail: str | None = None
    volatile_size: str | None = None


@dataclass
class DimmInfo:
    bytes: int = 0
    description: str | None = None
    handle: str | None = None
    type: int = 0
    values: DimmValues = field(default_factory=DimmValues)


@dataclass
class MemoryInfo:
    success: bool = False
    error: str | None = None
    available: int = 0
    buffers: int = 0
    buffers_cache: int = 0
    cached: int = 0
    dimms: list[DimmInfo] = field(default_factory=list)
    free: int = 0
    pct_free: int = 0
    pct_total: int = 0
    pct_used: int = 0
    shared: int = 0
    total: int = 0
    used: int = 0
    swap_pct_total: int = 0
    swap_pct_used: int = 0
    swap_pct_free: int = 0
    swap_total: int = 0
    swap_used: int = 0
    swap_free: int = 0
    updated: str | None = None
