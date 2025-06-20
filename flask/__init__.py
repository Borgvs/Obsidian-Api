import json
from types import SimpleNamespace

class _Request(SimpleNamespace):
    pass

request = _Request()

class Response:
    def __init__(self, data, status=200):
        if isinstance(data, (dict, list)):
            self.data = json.dumps(data).encode('utf-8')
        elif isinstance(data, bytes):
            self.data = data
        else:
            self.data = str(data).encode('utf-8')
        self.status_code = status

    def get_json(self):
        return json.loads(self.data.decode('utf-8'))

def jsonify(obj):
    return Response(obj, 200)

class Flask:
    def __init__(self, name):
        self.name = name
        self.routes = {}

    def route(self, rule, methods=None):
        methods = methods or ['GET']
        def decorator(func):
            self.routes.setdefault(rule, {})
            for m in methods:
                self.routes[rule][m] = func
            return func
        return decorator

    def test_client(self):
        app = self
        class Client:
            def __enter__(self_):
                return self_
            def __exit__(self_, exc_type, exc_val, exc_tb):
                pass
            def get(self_, path):
                return self_._request('GET', path)
            def post(self_, path, json=None):
                return self_._request('POST', path, json)
            def _match(self_, method, path):
                for rule, methods in app.routes.items():
                    if method not in methods:
                        continue
                    if '<path:filename>' in rule:
                        prefix = rule.split('<path:filename>')[0]
                        if path.startswith(prefix):
                            return methods[method], {'filename': path[len(prefix):]}
                    elif rule == path:
                        return methods[method], {}
                return None, None
            def _request(self_, method, path, json=None):
                func, kwargs = self_._match(method, path)
                if not func:
                    raise AssertionError(f'No route for {method} {path}')
                request.args = {}
                request.is_json = json is not None
                request.get_json = lambda: json
                result = func(**(kwargs or {}))
                if isinstance(result, tuple):
                    resp, status = result
                    resp.status_code = status
                    return resp
                return result
        return Client()

