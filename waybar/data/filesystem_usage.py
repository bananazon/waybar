from dataclasses import dataclass, field


@dataclass
class DFEntry:
    available: int = 0
    blocks: int = 0
    filesystem: str = ""
    free: int = 0
    free_percent: int = 0
    mounted_on: str | None = None
    use_percent: int = 0
    used: int = 0


@dataclass
class KvOptions:
    discard: str | None = None
    space_cache: str | None = None
    subvolid: str | None = None
    subvol: str | None = None


@dataclass
class FindMount:
    target: str | None = None
    source: str | None = None
    fstype: str | None = None
    options: list[str] = field(default_factory=list)
    kv_options: KvOptions = field(default_factory=KvOptions)


@dataclass
class DiskStatsSample:
    device: str | None = None
    discarding_time_ms: int = 0
    discards_completed_successfully: int = 0
    discards_merged: int = 0
    flush_requests_completed_successfully: int = 0
    flushing_time_ms: int = 0
    io_in_progress: int = 0
    io_time_ms: int = 0
    maj: int = 0
    min: int = 0
    read_time_ms: int = 0
    reads_completed: int = 0
    reads_merged: int = 0
    sectors_discarded: int = 0
    sectors_read: int = 0
    sectors_written: int = 0
    weighted_io_time_ms: int = 0
    write_time_ms: int = 0
    writes_completed: int = 0
    writes_merged: int = 0


@dataclass
class BlockDevice:
    alignment: int = 0
    dax: bool = False
    disc_aln: int = 0
    disc_gran: str | None = None
    disc_max: str | None = None
    disc_zero: bool = False
    disk_seq: int = 0
    fsavail: str | None = None
    fsroots: list[str] = field(default_factory=list)
    fssize: str | None = None
    fstype: str | None = None
    fsuse_pct: str | None = None
    fsused: str | None = None
    fsver: str | None = None
    group: str | None = None
    hctl: str | None = None
    hotplug: bool = False
    id: str | None = None
    id_link: str | None = None
    kname: str | None = None
    label: str | None = None
    log_sec: int = 0
    maj: str | None = None
    maj_min: str | None = None
    min: str | None = None
    min_io: int = 0
    mode: str | None = None
    model: str | None = None
    mountpoint: str | None = None
    mountpoints: list[str] = field(default_factory=list)
    mq: str | None = None
    name: str | None = None
    opt_io: int = 0
    owner: str | None = None
    partflags: str | None = None
    partlabel: str | None = None
    partn: int = 0
    parttype: str | None = None
    parttypename: str | None = None
    partuuid: str | None = None
    path: str | None = None
    phy_sec: int = 0
    pkname: str | None = None
    pttype: str | None = None
    ptuuid: str | None = None
    ra: int = 0
    rand: bool = False
    rev: str | None = None
    rm: bool = False
    ro: bool = False
    rota: bool = False
    rq_size: int = 0
    sched: str | None = None
    serial: str | None = None
    size: str | None = None
    start: int = 0
    state: str | None = None
    subsystems: str | None = None
    tran: str | None = None
    type: str | None = None
    uuid: str | None = None
    vendor: str | None = None
    wsame: str | None = None
    wwn: str | None = None
    zone_amax: int = 0
    zone_app: str | None = None
    zone_nr: int = 0
    zone_omax: int = 0
    zone_sz: str | None = None
    zone_wgran: str | None = None
    zoned: str | None = None


@dataclass
class FilesystemInfo:
    success: bool = False
    error: str | None = None
    filesystem: str | None = None
    free: int = 0
    fsopts: str | None = None
    fstype: str | None = None
    lsblk: BlockDevice = field(default_factory=BlockDevice)
    mountpoint: str | None = None
    pct_free: int = 0
    pct_total: int = 0
    pct_used: int = 0
    total: int = 0
    used: int = 0
    sample1: DiskStatsSample = field(default_factory=DiskStatsSample)
    sample2: DiskStatsSample = field(default_factory=DiskStatsSample)
    updated: str | None = None
