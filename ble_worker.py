import asyncio
import sys
from bleak import BleakClient

NOTIFY = '0000fff1-0000-1000-8000-00805f9b34fb'
WRITE = '0000fff2-0000-1000-8000-00805f9b34fb'


async def main(address):
    async with BleakClient(address, timeout=20) as client:
        queue = asyncio.Queue()
        await client.start_notify(NOTIFY, lambda _, data: queue.put_nowait(bytes(data)))
        print('READY', flush=True)
        while True:
            command = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not command:
                return
            await client.write_gatt_char(WRITE, command.strip() + b'\r', response=False)
            response = bytearray()
            async with asyncio.timeout(20):
                while b'>' not in response:
                    response.extend(await queue.get())
                    if len(response) > 65536:
                        raise OSError('Resposta BLE excedeu o limite.')
            sys.stdout.buffer.write(response)
            sys.stdout.buffer.flush()


try:
    asyncio.run(main(sys.argv[1]))
except Exception as exc:
    print(f'Erro BLE: {exc}', file=sys.stderr, flush=True)
    sys.exit(1)
