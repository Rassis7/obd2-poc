import json
import os
import plistlib
import tty
import termios
import fcntl
import select
import subprocess
import time
import sys
import socket
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


def read_until(fd, marker, timeout):
    end = time.monotonic() + timeout
    buf = bytearray()
    while marker not in buf:
        if not select.select([fd], [], [], max(0, end-time.monotonic()))[0]:
            raise TimeoutError('Tempo de resposta excedido: ' + buf.decode('ascii', 'replace'))
        chunk = os.read(fd, 4096)
        if not chunk:
            raise EOFError('Bluetooth desconectado.')
        buf.extend(chunk)
        if len(buf) > 65536:
            raise OSError('Resposta serial excedeu o limite.')
    return buf.decode('ascii', 'replace').rstrip('>')

def port_for_device(tree, address):
    expected = address.replace('-', '').replace(':', '').lower()
    for node in tree:
        if node.get('BD_ADDR') != bytes.fromhex(expected):
            continue
        children = list(node.get('IORegistryEntryChildren', []))
        while children:
            child = children.pop()
            port = child.get('IOCalloutDevice', '')
            if port.startswith('/dev/cu.'):
                return port
            children.extend(child.get('IORegistryEntryChildren', []))
    return None


class SerialLink:
    def __init__(self, port):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
            tty.setraw(self.fd)
        except BaseException:
            self.close()
            raise

    def query(self, cmd):
        data = cmd.encode('ascii') + b'\r'
        if os.write(self.fd, data) != len(data):
            raise OSError('Envio serial incompleto.')
        try:
            return read_until(self.fd, b'>', 20)
        except TimeoutError as err:
            raise TimeoutError(f'O adaptador não concluiu a resposta a {cmd} em 20 s. {err}') from err
        except EOFError as err:
            raise OSError(str(err)) from err

    def close(self):
        os.close(self.fd)


def Link(address):
    registry = subprocess.run(['/usr/sbin/ioreg','-a','-l','-r','-c','IOBluetoothDevice'],
                              capture_output=True, timeout=5)
    if registry.returncode == 0 and registry.stdout.strip():
        port = port_for_device(plistlib.loads(registry.stdout), address)
        if port and os.path.exists(port):
            return SerialLink(port)
    return NativeLink(address)


class NativeLink:
    def __init__(self, address):
        self.proc = subprocess.Popen([RADIO, address], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        try:
            if self.read_until(b'\n', 60).strip() != 'READY':
                raise OSError('Canal serial indisponível.')
        except TimeoutError as err:
            self.close()
            raise TimeoutError('O macOS não confirmou a abertura do canal Bluetooth em 60 s. '
                               'Confira a alimentação do adaptador e se outro app está conectado.') from err
        except Exception:
            self.close()
            raise

    def read_until(self, marker, timeout):
        try:
            return read_until(self.proc.stdout.fileno(), marker, timeout)
        except EOFError as err:
            raise OSError(self.proc.stderr.read().decode(errors='replace') or str(err)) from err

    def query(self, cmd):
        self.proc.stdin.write(cmd.encode('ascii') + b'\r')
        return self.read_until(b'>', 20)

    def close(self):
        self.proc.kill()
        self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()


class BleLink(NativeLink):
    def __init__(self, address):
        self.proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('ble_worker.py')), address],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, bufsize=0)
        try:
            if self.read_until(b'\n', 30).strip() != 'READY':
                raise OSError('Conexão BLE indisponível.')
        except Exception:
            self.close()
            raise

    def query(self, cmd):
        self.proc.stdin.write(cmd.encode('ascii') + b'\n')
        return self.read_until(b'>', 20)


class SandboxLink:
    def __init__(self, address):
        self.sock = socket.create_connection(('127.0.0.1', 35000), timeout=20)

    def query(self, cmd):
        self.sock.sendall(cmd.encode('ascii') + b'\r')
        return read_until(self.sock.fileno(), b'>', 20)

    def close(self):
        self.sock.close()
