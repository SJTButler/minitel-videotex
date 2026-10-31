"""TCP transport and paced writes."""

import asyncio


async def paced_write(writer, data, cps):
    if cps <= 0:
        writer.write(data)
        await writer.drain()
        return
    for i in range(0, len(data), 32):
        writer.write(data[i:i + 32])
        await writer.drain()
        if i + 32 < len(data):
            await asyncio.sleep(32 / cps)


async def serve(handler, host, port):
    return await asyncio.start_server(handler, host, port)
