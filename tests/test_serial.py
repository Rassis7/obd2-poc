import os
import pty
import threading
import unittest
from bluetooth_mac import SerialLink, port_for_device

class SerialTests(unittest.TestCase):
    def test_address_match(self):
        tree = [{'BD_ADDR':bytes.fromhex('010203040506'), 'IORegistryEntryChildren':[
            {'IOCalloutDevice':'/dev/cu.OBDII'}]}]
        self.assertEqual(port_for_device(tree, '01-02-03-04-05-06'), '/dev/cu.OBDII')
        self.assertIsNone(port_for_device(tree, '01-02-03-04-05-07'))

    def test_command(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        link = SerialLink(os.ttyname(slave))
        self.addCleanup(link.close)
        def respond():
            if os.read(master, 4) == b'ATI\r':
                os.write(master, b'ELM327 v1.5\r>')
        threading.Thread(target=respond,daemon=True).start()
        self.assertEqual(link.query('ATI'), 'ELM327 v1.5\r')

class BlePipeTest(unittest.TestCase):
    def test_ble_command_ends_with_newline_for_worker(self):
        import io
        from bluetooth_mac import BleLink
        link = BleLink.__new__(BleLink)
        link.proc = type('Process', (), {'stdin': io.BytesIO()})()
        link.read_until = lambda marker, timeout: 'ELM327 v1.5'
        self.assertEqual(link.query('ATI'), 'ELM327 v1.5')
        self.assertEqual(link.proc.stdin.getvalue(), b'ATI\n')
