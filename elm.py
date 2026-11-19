def frames(raw, prefix):
    """Extrai respostas curtas com eco desligado, cabeçalhos e espaços ligados."""
    rows = []
    pending = {}
    start = bytes.fromhex(prefix)
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            if len(parts[0]) in (3, 8):  # CAN 11 bits, PCI e carga
                ecu, data = parts[0], bytes.fromhex(' '.join(parts[1:]))

            elif len(parts) >= 6 and parts[0] in ('18', '19'):  # CAN 29 bits
                ecu = ''.join(parts[:4])
                data = bytes.fromhex(' '.join(parts[4:]))

            else:  # ISO/KWP/J1850, três bytes de cabeçalho
                ecu, payload = parts[2], bytes.fromhex(' '.join(parts[3:]))
                if payload.startswith(start):
                    rows.append((ecu, payload[len(start):]))
                continue
            if not data:
                continue
            kind = data[0] >> 4
            if kind == 0:
                payload = data[1:1+data[0]]
            elif kind == 1 and len(data) >= 2:
                pending[ecu] = (((data[0]&15)<<8) + data[1], bytearray(data[2:]), 1)
                continue
            elif kind == 2 and ecu in pending:
                size, buf, seq = pending.pop(ecu)
                if data[0]&15 != seq:
                    continue
                buf.extend(data[1:])
                if len(buf) < size:
                    pending[ecu] = (size, buf, (seq+1)%16)
                    continue
                payload = bytes(buf[:size])
            else:
                continue
        except ValueError:
            continue
        if payload.startswith(start):
            rows.append((ecu, payload[len(start):]))
    return rows


def supported(data, base):
    mask = int.from_bytes(data[:4], 'big')
    return [base+i for i in range(1, 33) if len(data) >= 4 and mask & (1 << (32-i))]


def decode(cmd, data):
    if not data:
        return None, None
    a = data[0]
    if cmd in ('0105', '010F', '015C'):
        return a - 40, '°C'
    if cmd in ('0104', '0111', '012F'):
        return a * 100 / 255, '%'
    if cmd in ('0106', '0107'):
        return (a - 128) * 100 / 128, '%'
    if cmd == '010D':
        return a, 'km/h'
    if cmd == '010B':
        return a, 'kPa'
    if len(data) >= 2:
        word = int.from_bytes(data[:2], 'big')
        if cmd == '010C':
            return word / 4, 'rpm'
        if cmd == '0142':
            return word / 1000, 'V'
        if cmd == '015E':
            return word / 20, 'L/h'
        if cmd == '0110':
            return word / 100, 'g/s'
    return None, None


def collect(query, save, stop):
    def ask(cmd, prefix=None, expected=()):
        if stop.is_set():
            raise InterruptedError
        try:
            raw = query(cmd)
        except OSError as err:
            save(dict(command=cmd, error=str(err)))
            raise
        rows = frames(raw, prefix) if prefix else []
        base = dict(command=cmd, raw=raw)
        if not rows:
            normalized = raw.strip().upper()
            error = next((s for s in ('NO DATA','UNABLE TO CONNECT','CAN ERROR','BUS ERROR','STOPPED','?') if s in normalized), None)
            save(dict(base, error=error))
        for ecu, data in rows:
            value, unit = decode(cmd, data)
            save(dict(base, ecu=ecu, value=value, unit=unit))
        for missing in set(expected) - {ecu for ecu, _ in rows}:
            save(dict(base, ecu=missing, error='Sem resposta identificada da central'))
        return rows, raw

    for cmd in ('ATZ','ATE0','ATL0','ATS1','ATH1','ATSP0','ATI','ATRV'):
        _, raw = ask(cmd)
        if cmd not in ('ATI','ATRV','ATZ') and 'OK' not in raw.upper():
            raise OSError(f'Configuração recusada: {cmd}')
    live = []
    for mode in (1, 2, 9, 6):
        for offset in range(0, 256, 32):
            pid = f'{offset:02X}'
            suffix = '00' if mode == 2 else ''
            cmd = f'{mode:02X}{pid}{suffix}'
            prefix = f'{64+mode:02X}{pid}{suffix}'
            rows, _ = ask(cmd, prefix)
            if mode == 1 and offset == 0 and not rows:
                raise OSError('Adaptador conectado, mas a central não respondeu ao inventário OBD-II.')
            announced = {}
            for ecu, data in rows:
                pids = supported(data, offset)
                for number in pids:
                    announced.setdefault(number, set()).add(ecu)
                save(dict(command=cmd, ecu=ecu, supported=pids))
            for number in sorted(announced):
                if number % 32:
                    request = f'{mode:02X}{number:02X}{suffix}'
                    reply = f'{64+mode:02X}{number:02X}{suffix}'
                    ask(request, reply, announced[number])
                    if mode == 1:
                        live.append((request, reply, announced[number]))
            if offset+32 not in announced:
                break
    _, protocol = ask('ATDPN')
    if protocol.strip().upper().removeprefix('A') in ('1','2','3','4','5'):
        # Mode 05 addresses each oxygen sensor separately.
        for sensor in range(1, 9):
            for offset in range(0, 256, 32):
                key = f'{offset:02X}{sensor:02X}'
                rows, _ = ask('05'+key, '45'+key)
                tests = set()
                for ecu, data in rows:
                    ids = supported(data, offset)
                    save(dict(command='05'+key, ecu=ecu, supported=ids))
                    tests.update(ids)
                for tid in sorted(tests):
                    if tid % 32:
                        key = f'{tid:02X}{sensor:02X}'
                        ask('05'+key, '45'+key)
                if offset+32 not in tests:
                    break
    for cmd in ('03','07','0A'):
        ask(cmd)
    while not stop.wait(.2):
        responding = False
        for cmd, prefix, expected in live:
            rows, _ = ask(cmd, prefix, expected)
            responding |= bool(rows)
        if live and not responding:
            save(dict(event="ecu_silent"))
        ask('ATRV')
