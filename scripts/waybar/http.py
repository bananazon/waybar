from collections.abc import MutableMapping
from dataclasses import dataclass, field
from http.client import HTTPResponse
from typing import cast
import json
import time
import urllib.error
import urllib.parse
import urllib.request


@dataclass
class Response:
    status: int = 0
    headers: dict[str, object] = field(default_factory=dict)
    body: str | None = None


def request(
    url: str,
    method: str,
    headers: MutableMapping[str, str] | None = None,
    params: dict[str, object] | None = None,
    data: dict[str, object] | str | None = None,
    timeout: float = 5.0,  # 5
    retries: int = 3,  # 3
    retry_delay: float = 1.0,  # 1
) -> Response | None:
    """
    Robust HTTP request function.

    Args:
        url (str): The URL to request.
        method (str): HTTP method ('GET', 'POST', etc.).
        headers (dict): Optional HTTP headers.
        params (dict): Query parameters for GET requests.
        data (dict or str): Request body (dict will be JSON-encoded).
        timeout (float): Timeout in seconds.
        retries (int): Number of retry attempts on failure.
        retry_delay (float): Delay between retries in seconds.

    Returns:
        dict: {
            'status': int,
            'headers': dict,
            'body': dict (if JSON) or str
        } or None on failure
    """
    json_data: bytes | None = None

    if params and method.upper() == "GET":
        query_string = urllib.parse.urlencode(params)
        url = f"{url}?{query_string}"

    if data:
        if isinstance(data, dict):
            json_data = json.dumps(data).encode("utf-8")
            headers = headers or {}
            headers["Content-Type"] = "application/json"

    headers = headers or {}

    for attempt in range(1, retries + 1):
        try:
            if json_data is not None:
                request = urllib.request.Request(
                    url, data=bytes(json_data), headers=headers, method=method
                )
            else:
                request = urllib.request.Request(url, headers=headers, method=method)

            with urllib.request.urlopen(request, timeout=timeout) as resp_any:
                response = cast(HTTPResponse, resp_any)
                body = response.read().decode("utf-8").strip()

                return Response(
                    status=response.status,
                    headers=dict(response.getheaders()),
                    body=body,
                )

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(retry_delay)
            else:
                return None
