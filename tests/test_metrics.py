import unittest

from elm import decode


class MetricsTests(unittest.TestCase):
    def test_mode_01_measurements(self):
        cases = [
            ('0104','ff',100,'%'), ('0111','00',0,'%'), ('010F','1e',-10,'°C'),
            ('0142','36b0',14,'V'), ('015E','00c8',10,'L/h'), ('012F','66',40,'%'),
            ('015C','82',90,'°C'), ('010B','64',100,'kPa'), ('0110','04d2',12.34,'g/s'),
            ('0106','60',-25,'%'), ('0107','a0',25,'%'),
        ]
        for cmd, raw, expected, unit in cases:
            with self.subTest(cmd=cmd):
                data = bytes.fromhex(raw)
                self.assertEqual(decode(cmd,data), (expected,unit))
                self.assertEqual(decode(cmd,data[:-1]), (None,None))

    def test_reprocess_matches_original_ecu(self):
        from reprocess import enrich
        row = dict(command='015E', ecu='7E9', time='original',
                   raw='7E8 04 41 5E 00 64\r7E9 04 41 5E 00 C8')
        self.assertEqual(enrich(row), dict(row, value=10, unit='L/h'))
        self.assertEqual(enrich({'event':'stop'}), {'event':'stop'})
