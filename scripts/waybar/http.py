from collections import namedtuple
from pprint import pprint
import json
import time
import urllib.error
import urllib.parse
import urllib.request

def dict_to_namedtuple(name, d):
    """Convert a dictionary to a namedtuple, with safe field names."""
    # Replace invalid characters in keys with underscore
    fields = [k.replace('-', '_').replace(' ', '_') for k in d.keys()]
    NT = namedtuple(name, fields)
    return NT(**d)

# Response namedtuple
HTTPResponse = namedtuple('HTTPResponse', ['status', 'headers', 'body'])

def request(
    url         : str  = None,
    method      : str  = 'GET',
    headers     : dict = None,
    params      : dict = None,
    data        : dict = None,
    timeout     : int  = 5,
    retries     : int  = 3,
    retry_delay : int = 1
):
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
    if params and method.upper() == 'GET':
        query_string = urllib.parse.urlencode(params)
        url = f'{url}?{query_string}'
    
    if data is not None:
        if isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
            headers = headers or {}
            headers['Content-Type'] = 'application/json'
        elif isinstance(data, str):
            data = data.encode('utf-8')

    headers = headers or {}

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_body = response.read().decode('utf-8').strip()
                try:
                    body = json.loads(raw_body)
                except json.JSONDecodeError:
                    body = raw_body

                return HTTPResponse(
                    status=response.status,
                    headers=dict(response.getheaders()),
                    body=body
                )

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"Attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(retry_delay)
            else:
                return None