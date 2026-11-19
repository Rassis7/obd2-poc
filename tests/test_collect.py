import threading
import unittest
from elm import collect, frames


class CaptureTest(unittest.TestCase):
    def test_multiframe_sources(self):
        raw = '7E8 10 09 49 02 01 41 42 43\r7E9 03 49 02 01\r7E8 21 44 45 46 00 00 00 00'
        self.assertIn(('7E8', bytes.fromhex('01414243444546')), frames(raw,'4902'))

    def test_capture_inventory_and_errors(self):
        stop = threading.Event()
        records = []
        def query(cmd):
            if cmd == '0A':
                stop.set()
            return {'0100':'7E8 06 41 00 00 18 00 01\r7E9 06 41 00 00 08 00 00',
                    '0120':'7E8 06 41 20 80 00 00 00',
                    '010D':'7E8 03 41 0D 00', '0121':'7E8 04 41 21 01 FF'}.get(
                        cmd, 'OK' if cmd.startswith('AT') else 'NO DATA')
        collect(query, records.append, stop)
        self.assertTrue(any(r.get('command')=='0121' and r.get('raw') for r in records))
        self.assertTrue(any(r.get('command')=='010D' and r.get('ecu')=='7E9' and r.get('error') for r in records))

    def test_compact_can_response(self):
        self.assertEqual(frames('7E804410C0B9C\r', '410C'), [('7E8', bytes.fromhex('0B9C'))])
