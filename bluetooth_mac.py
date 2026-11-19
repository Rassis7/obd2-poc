import json
import os
import select
import subprocess
import time
from pathlib import Path

RADIO = Path(__file__).resolve().parent / '.build/radio'


def devices(output):
    found = {}
    for line in output.splitlines():
        item = json.loads(line)
        found[item['id']] = item
    return list(found.values())


def scan():
    result = subprocess.run([RADIO], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise OSError(result.stderr.strip() or 'Busca Bluetooth interrompida.')
    return devices(result.stdout)


class Link:
    def __init__(self, address):
        self.proc = subprocess.Popen([RADIO, address], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        try:
            if self.read_until(b'\n', 60).strip() != 'READY':
                raise OSError('Canal serial indisponível.')
        except Exception:
            self.close()
            raise

    def read_until(self, marker, timeout):
        end = time.monotonic() + timeout
        buf = bytearray()
        while marker not in buf:
            if not select.select([self.proc.stdout], [], [], max(0, end-time.monotonic()))[0]:
                raise TimeoutError('Tempo de resposta excedido: ' + buf.decode('ascii', 'replace'))
            chunk = os.read(self.proc.stdout.fileno(), 4096)
            if not chunk:
                raise OSError(self.proc.stderr.read().decode(errors='replace') or 'Bluetooth desconectado.')
            buf.extend(chunk)
            if len(buf) > 65536:
                raise OSError('Resposta serial excedeu o limite.')
        return buf.decode('ascii', 'replace').rstrip('>')

    def query(self, cmd):
        self.proc.stdin.write(cmd.encode('ascii') + b'\r')
        return self.read_until(b'>', 20)

    def close(self):
        self.proc.kill()
        self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()
