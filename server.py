import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bluetooth_mac
from session import Session

ROOT = Path(__file__).resolve().parent
session = Session()
found = {}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, mime='application/json'):
        body = json.dumps(data, ensure_ascii=False).encode() if mime == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def stream_events(self):
        source = session
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        revision = -1
        try:
            while True:
                with source.changed:
                    if source.changed.wait_for(lambda: source.revision != revision, timeout=15):
                        revision = source.revision
                        event = 'data: ' + json.dumps(source.state) + '\n\n'
                    else:
                        event = ': heartbeat\n\n'
                self.wfile.write(event.encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {})
        if self.path == '/':
            return self.reply(200, (ROOT/'web/index.html').read_bytes(), 'text/html')
        if self.path == '/api/events':
            return self.stream_events()
        if self.path == '/api/state':
            with session.lock:
                data = {**session.state, 'sensors':session.state['sensors'].copy()}
            return self.reply(200, data)
        self.reply(404, {})

    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != 'http://' + self.headers['Host']:
            return self.reply(403, {})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 1024:
                raise ValueError('Pedido inválido.')
            body = json.loads(self.rfile.read(size) or b'{}')
            if self.path == '/api/scan':
                rows = bluetooth_mac.scan()
                with session.lock:
                    found.clear()
                    found.update({d['id']:d for d in rows})
                return self.reply(200, rows)
            if self.path == '/api/connect':
                with session.lock:
                    device = found.get(body.get('id')) if isinstance(body, dict) else None
                    if not device or device['transport'] != 'classic':
                        raise ValueError('Selecione um dispositivo Bluetooth clássico da busca.')
                    session.start(device['id'], bluetooth_mac.Link, ROOT/'sessoes')
            elif self.path == '/api/stop':
                session.end()
            else:
                return self.reply(404, {})
        except ValueError as exc:
            return self.reply(400, {'error':str(exc)})
        except Exception as exc:
            return self.reply(503, {'error':str(exc)})
        self.reply(200, {})


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Dashboard em http://127.0.0.1:8765', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        session.end()
        if session.thread:
            session.thread.join()
    finally:
        server.server_close()
