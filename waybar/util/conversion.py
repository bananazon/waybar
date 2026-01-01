import re
from typing import cast


def valid_storage_units() -> list[str]:
    """
    Return a list of valid units of storage.
    """
    return [
        "K",
        "Ki",
        "M",
        "Mi",
        "G",
        "Gi",
        "T",
        "Ti",
        "P",
        "Pi",
        "E",
        "Ei",
        "Z",
        "Zi",
        "auto",
    ]


def pad_float(number: float = 0.0, round_int: bool = False) -> str:
    """
    Pad a float to two decimal places.
    """
    if isinstance(number, int) and round_int:
        return str(int(number))
    else:
        return f"{number:.2f}"


def byte_converter(number: float, unit: str = "auto", use_int: bool = False) -> str:
    """
    Convert bytes to the given unit.
    """
    if unit is None:
        unit = "auto"
    suffix = "B"

    if unit == "auto":
        for unit_prefix in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]:
            if abs(number) < 1024.0:
                return (
                    f"{pad_float(number=number, round_int=False)} {unit_prefix}{suffix}"
                )
            number /= 1024
        return f"{pad_float(number=number, round_int=False)} Yi{suffix}"
    else:
        divisor: int = 1000
        if len(unit) == 2 and unit.endswith("i"):
            divisor = 1024

        prefix_map: dict[str, int] = {
            "K": 1,
            "Ki": 1,
            "M": 2,
            "Mi": 2,
            "G": 3,
            "Gi": 3,
            "T": 4,
            "Ti": 4,
            "P": 5,
            "Pi": 5,
            "E": 6,
            "Ei": 6,
            "Z": 7,
            "Zi": 7,
            "Y": 8,
            "Yi": 8,
        }

        if unit in prefix_map:
            power: int = prefix_map[unit]
            value = cast(float, number / (divisor**power))
            if use_int:
                return f"{int(value)} {unit}{suffix}"
            else:
                return f"{pad_float(value, round_int=False)} {unit}{suffix}"
        else:
            return f"{number} {suffix}"


def process_bytes(num: float) -> str:
    """
    Process the rate of data, e.g., MiB/s.
    """
    suffix = "B"
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{pad_float(num, round_int=False)} {unit}{suffix}/s"
        num = num / 1024
    return f"{pad_float(number=num, round_int=False)} Yi{suffix}"


def mhz_to_hz(number: float) -> float:
    return number * 1000000


def processor_speed(number: float) -> str | None:
    """
    Intelligently determine processor speed
    """
    # psutil reports the number in MHz so we convert to Hz
    number = mhz_to_hz(number=number)
    suffix = "Hz"

    for unit in ["", "K", "M", "G", "T"]:
        if abs(number) < 1000.0:
            return f"{pad_float(number=number, round_int=False)} {unit}{suffix}"
        number = number / 1000


def float_to_pct(number: float = 0) -> str:
    """
    Convert a floating point number to its percent equivalent.
    """
    return f"{number:.2f}%"


def to_snake_case(name: str) -> str:
    # Strip quotes
    name = re.sub(r"\"", "", name.strip())

    # Trim and replace spaces (and multiple spaces) with underscores
    name = re.sub(r"\s+", "_", name.strip())

    # Trim and replace hyphens with underscores
    name = re.sub(r"-+", "_", name.strip())

    # Handle CamelCase / PascalCase properly (keeps acronyms intact)
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)

    return name.lower()


def km_to_m(number: float) -> str:
    return pad_float(number=number * 0.62137119)
