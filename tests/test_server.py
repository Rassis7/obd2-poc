import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import server
from session import Session


class SimulatedLink:
    def __init__(self, address):
        pass

    def query(self, cmd):
        return {'0100':'7E8 06 41 00 08 18 00 00', '010C':'7E8 04 41 0C 0C 80',
                '0105':'7E8 03 41 05 70', '010D':'7E8 03 41 0D 00',
                'ATRV':'12.5V'}.get(cmd, 'OK' if cmd.startswith('AT') else 'NO DATA')

    def close(self):
        pass


class ServerTests(unittest.TestCase):
    def test_session(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'ROOT', Path(tmp)), \
                patch.object(server, 'session', Session()), patch.object(server.bluetooth_mac, 'Link', SimulatedLink), \
                patch.object(server.bluetooth_mac, 'scan', return_value=[dict(id='a', name='Teste', transport='classic')]):
            s = server.ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
            threading.Thread(target=s.serve_forever, daemon=True).start()
            self.addCleanup(s.server_close)
            self.addCleanup(s.shutdown)
            base = f'http://127.0.0.1:{s.server_port}'
            def post(action, origin=base):
                req = Request(base+'/api/'+action, data=b'{"id":"a"}', headers={'Origin':origin})
                with urlopen(req) as resp:
                    return json.load(resp)
            with self.assertRaises(HTTPError) as denied:
                post('connect','http://example.org')
            denied.exception.close()
            self.assertEqual(post('scan')[0]['id'],'a')
            post('connect')
            for _ in range(50):
                with urlopen(base+'/api/state') as resp:
                    state=json.load(resp)
                if state['sensors'].get('010D'):
                    break
                time.sleep(.02)
            self.assertEqual(state['sensors']['010D']['value'],0)
            path=Path(state['path'])
            length=path.stat().st_size
            time.sleep(.4)
            self.assertGreater(path.stat().st_size,length)
            post('stop')
            server.session.thread.join(2)
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])['event'],'stop')

    def test_disconnect_keeps_file(self):
        class BrokenLink(SimulatedLink):
            def query(self, cmd):
                raise OSError('link perdido')
        with tempfile.TemporaryDirectory() as tmp:
            session = Session()
            session.start('a', BrokenLink, tmp)
            session.thread.join(2)
            self.assertIn('link perdido',session.state['status'])
            rows=[json.loads(line) for line in Path(session.state['path']).read_text().splitlines()]
            self.assertEqual(rows[1]['command'],'ATZ')
            self.assertEqual(rows[-1]['event'],'error')

    def test_unwritable_destination(self):
        with tempfile.NamedTemporaryFile() as target:
            session = Session()
            session.start('a', SimulatedLink, target.name)
            session.thread.join(2)
            self.assertTrue(session.state['status'].startswith('Erro:'))
            self.assertFalse(session.state['adapter'])
