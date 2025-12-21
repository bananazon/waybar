from dataclasses import dataclass, field


@dataclass
class CacheValues:
    associativity: str | None = None
    configuration: str | None = None
    error_correction_type: str | None = None
    install_sram_type: str | None = None
    installed_size: str = ""
    location: str | None = None
    maximum_size: str | None = None
    operational_mode: str | None = None
    socket_designation: str | None = None
    supported_sram_types: list[str] = field(default_factory=list)
    speed: str | None = None
    system_type: str | None = None


@dataclass
class CpuCache:
    handle: str | None = None
    type: int = 0
    bytes: int = 0
    description: str | None = None
    values: CacheValues = field(default_factory=CacheValues)


@dataclass
class CoreInfo:
    tlb_size: str | None = None
    address_sizes: str | None = None
    address_size_physical: str | None = None
    address_size_virtual: str | None = None
    apicid: int = 0
    bogomips: float = 0.0
    bugs: list[str] = field(default_factory=list)
    cache_size: str | None = None
    cache_alignment: int = 0
    cache_size_num: int = 0
    cache_size_unit: str | None = None
    clfush_size: int = 0
    core_id: int = 0
    cpu_cores: int = 0
    cpu_family: int = 0
    cpu_frequency: float = 0.0
    cpuid_level: int = 0
    flags: list[str] = field(default_factory=list)
    fpu: bool = False
    fpu_exception: bool = False
    initial_apicid: int = 0
    microcode: str | None = None
    model_name: str | None = None
    model: int = 0
    physical_id: int = 0
    power_management: str | None = None
    processor: int = 0
    siblings: int = 0
    stepping: int = 0
    vendor_id: str | None = None
    wp: bool = False


@dataclass
class CorePercent:
    cpu: str | None = None
    percent_usr: float = 0.0
    percent_nice: float = 0.0
    percent_sys: float = 0.0
    percent_iowait: float = 0.0
    percent_irq: float = 0.0
    percent_soft: float = 0.0
    percent_steal: float = 0.0
    percent_guest: float = 0.0
    percent_gnice: float = 0.0
    percent_idle: float = 0.0
    type: str | None = None
    timestamp: str | None = None


@dataclass
class CpuInfo:
    success: bool = False
    error: str | None = None
    caches: list[CpuCache] = field(default_factory=list)
    cores_logical: int = 0
    cores_physical: int = 0
    cpu_load: list[CorePercent] = field(default_factory=list)
    freq_cur: float = 0.0
    freq_max: float = 0.0
    freq_min: float = 0.0
    model: str | None = None
    updated: str | None = None
