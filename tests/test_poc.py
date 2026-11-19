import json
import tempfile
import unittest
from pathlib import Path
from elm import frames, supported, decode
from session import Journal
from bluetooth_mac import devices

class PocTests(unittest.TestCase):
    def test_inventory(self):
        replies = frames('7E8 06 41 00 00 18 00 01\r7E9 06 41 00 08 00 00 00', '4100')
        self.assertEqual(supported(replies[0][1], 0), [12, 13, 32])
        self.assertEqual(replies[1][0], '7E9')
        self.assertEqual(decode('010D', bytes([0])), (0, 'km/h'))
        self.assertEqual(frames('NO DATA', '410D'), [])

    def test_log(self):
        with tempfile.TemporaryDirectory() as d:
            with Journal(Path(d)) as log:
                log.write({'raw':'NO DATA'})
                self.assertEqual(json.loads(log.path.read_text())['raw'], 'NO DATA')
            with Journal(Path(d)) as other:
                self.assertNotEqual(log.path, other.path)

    def test_devices(self):
        rows = devices('{"id":"a","name":"OBD","transport":"classic"}\n{"id":"b","name":"OBD","transport":"ble"}')
        self.assertEqual(len(rows), 2)
