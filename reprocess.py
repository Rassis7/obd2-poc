import json
import sys
from pathlib import Path

from elm import decode, frames


def map_limits(src):
    limits = {}
    for line in src:
        row = json.loads(line)
        ecu = row.get('ecu')
        if row.get('command') == '0140' and 79 in row.get('supported', []):
            limits.setdefault(ecu, None)
        if row.get('command') == '014F' and ecu and not row.get('error'):
            for origin, data in frames(row.get('raw', ''), '414F'):
                if origin == ecu and len(data) >= 4:
                    limits[ecu] = data[3]*10 or 255
    src.seek(0)
    return limits


def enrich(row, map_max_kpa=255):
    cmd = row.get('command', '')
    if cmd.startswith('01') and row.get('ecu') and row.get('raw') and not row.get('error'):
        for ecu, data in frames(row['raw'], '41' + cmd[2:]):
            if ecu == row['ecu']:
                value, unit = decode(cmd, data, map_max_kpa)
                if value is not None or cmd == '010B':
                    return dict(row, value=value, unit=unit)
    return row


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Uso: python3 reprocess.py caminho/arquivo.jsonl')
    source = Path(sys.argv[1])
    target = source.with_suffix('.decodificado.jsonl')
    with source.open(encoding='utf8') as src, target.open('x', encoding='utf8') as dst:
        try:
            limits = map_limits(src)
            for line in src:
                row = json.loads(line)
                dst.write(json.dumps(enrich(row, limits.get(row.get('ecu'), 255)), ensure_ascii=False) + '\n')
        except BaseException:
            target.unlink()
            raise
    print(target)
