import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from elm import collect


def now():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / (uuid.uuid4().hex + '.jsonl')

    def __enter__(self):
        self.file = self.path.open('x', encoding='utf8')
        return self

    def write(self, row):
        self.file.write(json.dumps(row, ensure_ascii=False) + '\n')
        self.file.flush()

    def __exit__(self, *args):
        self.file.close()


class Session:
    def __init__(self):
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.revision = 0
        self.thread = None
        self.state = dict(status='Parado', adapter=False, ecu=False, sensors={})

    def publish(self):
        # Caller holds the session lock while changing the shared state.
        self.revision += 1
        self.changed.notify_all()

    def start(self, address, factory, folder):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('Uma sessão já está ativa.')
            self.stop = threading.Event()
            self.state = dict(status='Conectando', adapter=False, ecu=False, sensors={})
            self.publish()
            self.thread = threading.Thread(target=self.run, args=(address,factory,folder), daemon=True)
            self.thread.start()

    def end(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.stop.set()

    def run(self, address, factory, folder):
        link = None
        try:
            with Journal(Path(folder)) as log:
                def record(row):
                    row['time'] = now()
                    log.write(row)
                    with self.lock:
                        if row.get('ecu') and not row.get('error') and not self.state['ecu']:
                            self.state.update(ecu=True, status='Lendo central')
                        if row.get('event') == 'ecu_silent':
                            self.state.update(ecu=False, status='Central sem resposta')
                        cmd = row.get('command', '')
                        sensors = self.state['sensors']
                        if cmd.startswith('01') and 'supported' in row:
                            for pid in row['supported']:
                                sensors.setdefault(f'01{pid:02X}', None)
                        if cmd in sensors and row.get('ecu') and row.get('value') is None:
                            previous = sensors[cmd]
                            if previous and previous['ecu'] == row['ecu']:
                                sensors[cmd] = None
                        if row.get('value') is not None:
                            self.state['sensors'][row['command']] = row
                        self.publish()
                with self.lock:
                    self.state['path'] = str(log.path.resolve())
                record(dict(event='start', device=address))
                try:
                    link = factory(address)
                    with self.lock:
                        self.state.update(adapter=True, status='Consultando central')
                        self.publish()
                    collect(link.query, record, self.stop)
                except InterruptedError:
                    pass
                except Exception as exc:
                    record(dict(event='error', error=str(exc)))
                    raise
                record(dict(event='stop'))
            status = 'Encerrado'
        except Exception as exc:
            status = f'Erro: {exc}'
        finally:
            if link:
                link.close()
            with self.lock:
                self.state.update(status=status, ecu=False, adapter=False)
                self.publish()
