import json
import sys
from pathlib import Path

from elm import decode, frames


def enrich(row):
    cmd = row.get('command', '')
    if cmd.startswith('01') and row.get('ecu') and row.get('raw') and not row.get('error'):
        for ecu, data in frames(row['raw'], '41' + cmd[2:]):
            if ecu == row['ecu']:
                value, unit = decode(cmd, data)
                if value is not None:
                    return dict(row, value=value, unit=unit)
    return row


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Uso: python3 reprocess.py caminho/arquivo.jsonl')
    source = Path(sys.argv[1])
    target = source.with_suffix('.decodificado.jsonl')
    with source.open(encoding='utf8') as src, target.open('x', encoding='utf8') as dst:
        try:
            for line in src:
                dst.write(json.dumps(enrich(json.loads(line)), ensure_ascii=False) + '\n')
        except BaseException:
            target.unlink()
            raise
    print(target)
