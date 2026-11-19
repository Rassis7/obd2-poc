import unittest
from elm import decode

class DatasetTest(unittest.TestCase):
    def test_real_samples(self):
        for cmd, raw, expected in [('0152','66',(40,'%')), ('013C','0bf4',(266,'°C')),
                                   ('0123','030c',(7800,'kPa')), ('010E','74',(-6,'°'))]:
            with self.subTest(cmd=cmd):
                self.assertEqual(decode(cmd,bytes.fromhex(raw)),expected)

    def test_optional_subfields(self):
        self.assertEqual(decode('0114',bytes.fromhex('64ff')),({'voltage_V':0.5},None))
        self.assertEqual(decode('0168',bytes.fromhex('02003f00000000')),({'b1s2_C':23},None))
        self.assertEqual(decode('016D',b'\x01'),(None,None))

    def test_map_uses_ecu_scale(self):
        self.assertEqual(decode('010B',bytes([255]),440),(440,'kPa'))
        self.assertEqual(decode('010B',bytes([255]),None),(None,None))
