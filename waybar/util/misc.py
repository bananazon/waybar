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


def str_hook(v: str | None):
    if v is None:
        return None
    return str(v)


def int_hook(v: int | None):
    if v is None:
        return 0  # or None if your field is Optional[int]
    return int(v)
