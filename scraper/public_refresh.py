"""Best-effort, authenticated invalidation after a committed public-data change."""
import os
from urllib.parse import urlsplit
import requests


def refresh_public_data(*, companies=None, scopes=None):
    endpoint = os.environ.get('IVR_REVALIDATE_URL')
    secret = os.environ.get('IVR_REVALIDATE_SECRET')
    if not endpoint or not secret:
        return 'not_configured'
    url = urlsplit(endpoint)
    local = url.hostname in ('127.0.0.1', 'localhost', '::1')
    if url.username or url.password or (url.scheme != 'https' and not (url.scheme == 'http' and local)):
        return 'invalid_configuration'
    body = {}
    if companies:
        body['companies'] = sorted(set(companies))[:100]
    if scopes:
        body['scopes'] = list(dict.fromkeys(scopes))
    if not body:
        return 'no_changes'
    try:
        response = requests.post(endpoint, json=body, headers={'Authorization': 'Bearer '+secret},
                                 timeout=8, allow_redirects=False)
        return 'refreshed' if response.status_code == 200 else 'failed'
    except requests.RequestException:
        # The timed cache refresh is the fallback. Never log a URL/token/response.
        return 'failed'
