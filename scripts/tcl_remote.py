#!/usr/bin/env python3
import sys
import asyncio
sys.path.insert(0, "/tmp/ha-tcl-tv/custom_components/tcl_tv")
from protocol import TclTvClient, KEYS

TV_IP = "192.168.100.101"

async def send_keys(key_list, delay=0.3):
    client = TclTvClient(TV_IP, "antigravity", "ag-remote")
    info = await client.connect()
    print(f"Connected to TV: {info.model}")
    for k in key_list:
        code = KEYS.get(str(k))
        if code is None:
            print(f"Unknown key: {k}")
            continue
        print(f"Sending key: {k} (code {code})")
        await client.send_key(code)
        await asyncio.sleep(delay)
    await client.close()
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tcl_remote.py <key1> <key2> ...")
        print("Available keys:", list(KEYS.keys()))
        sys.exit(1)
    asyncio.run(send_keys(sys.argv[1:]))
