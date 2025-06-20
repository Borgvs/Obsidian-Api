def request(*args, **kwargs):
    raise RuntimeError('network disabled')

def get(*args, **kwargs):
    return request(*args, **kwargs)

def put(*args, **kwargs):
    return request(*args, **kwargs)

from .auth import HTTPBasicAuth
