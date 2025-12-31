from dataclasses import dataclass, field


@dataclass
class DHCPClass:
    dhcp_domain_name: str | None = None
    dhcp_domain_name_servers: str | None = None
    dhcp_lease_duration: int = 0
    dhcp_message_type: str | None = None
    dhcp_routers: str | None = None
    dhcp_server_identifier: str | None = None
    dhcp_subnet_mask: str | None = None


@dataclass
class DNSClass:
    DomainName: str | None = None
    ServerAddresses: list[str] = field(default_factory=list)


@dataclass
class EthernetClass:
    MacAddress: str | None = None
    MediaOptions: list[str] = field(default_factory=list)
    MediaSubType: str | None = None


@dataclass
class AdditionalRoute:
    DestinationAddress: str | None = None
    SubnetMask: str | None = None


@dataclass
class NetworkDataTypeItemIPv4:
    AdditionalRoutes: list[AdditionalRoute] = field(default_factory=list)
    Addresses: list[str] = field(default_factory=list)
    ARPResolvedHardwareAddress: str | None = None
    ARPResolvedIPAddress: str | None = None
    ConfigMethod: str | None = None
    ConfirmedInterfaceName: str | None = None
    InterfaceName: str | None = None
    NetworkSignature: str | None = None
    NetworkSignatureHash: str | None = None
    Router: str | None = None


@dataclass
class NetworkDataTypeItemIPv6:
    AdditionalRoutes: list[AdditionalRoute] = field(default_factory=list)
    Addresses: list[str] = field(default_factory=list)
    ARPResolvedHardwareAddress: str | None = None
    ARPResolvedIPAddress: str | None = None
    ConfigMethod: str | None = None
    ConfirmedInterfaceName: str | None = None
    InterfaceName: str | None = None
    NetworkSignature: str | None = None
    NetworkSignatureHash: str | None = None
    Router: str | None = None
    SubnetMasks: list[str] = field(default_factory=list)


@dataclass
class NetworkDataTypeItemProxies:
    ExceptionsList: list[str] = field(default_factory=list)
    ExcludeSimpleHostnames: int = 0
    FTPEnable: str | bool | None = None
    FTPPassive: str | bool | None = None
    FTPPort: int = 0
    FTPProxy: str | None = None
    HTTPEnable: str | bool | None = None
    HTTPPort: int = 0
    HTTPProxy: str | None = None
    HTTPSEnable: str | bool | None = None
    HTTPSPort: int = 0
    HTTPSProxy: str | None = None
    ProxyAutoConfigEnable: str | bool | None = None
    ProxyAutoConfigURLString: str | None = None
    ProxyAutoDiscoveryEnable: str | bool | None = None
    SOCKSEnable: str | None = None
    SOCKSPort: int = 0
    SOCKSProxy: str | None = None


@dataclass
class NetworkDataTypeItem:
    name: str = ""
    dhcp: DHCPClass = field(default_factory=DHCPClass)
    DNS: DNSClass = field(default_factory=DNSClass)
    Ethernet: EthernetClass = field(default_factory=EthernetClass)
    hardware: str = ""
    interface: str = ""
    ip_address: list[str] = field(default_factory=list)
    IPv4: NetworkDataTypeItemIPv4 = field(default_factory=NetworkDataTypeItemIPv4)
    IPv6: NetworkDataTypeItemIPv6 = field(default_factory=NetworkDataTypeItemIPv6)
    Proxies: NetworkDataTypeItemProxies = field(
        default_factory=NetworkDataTypeItemProxies
    )
    spnetwork_service_order: int = 0
    type: str = ""


@dataclass
class NetworkDataType:
    SPNetworkDataType: list[NetworkDataTypeItem] = field(default_factory=list)
