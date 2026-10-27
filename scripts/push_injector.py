#!/usr/bin/env python3
import functools
import hashlib
import http.server
import os
import socket
import struct
import sys
import threading
import time

PORT = 6553
SERVE_PORT = 8765
PACKAGE = "jackpal.androidterm"
LABEL = "终端模拟器"
VERSION = "75"
APK_PATH = "/tmp/terminal_fixed.apk"
TV_IP = "192.168.100.101"

def send(sock, text):
    data = text.encode()
    sock.sendall(struct.pack(">i", len(data)) + data)

def messages(buf):
    out = []
    while len(buf) >= 4:
        n = struct.unpack(">i", buf[:4])[0]
        if len(buf) < 4 + n:
            break
        out.append(buf[4:4 + n].decode("utf-8", "replace"))
        buf = buf[4 + n:]
    return out, buf

def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((TV_IP, PORT))
        me = s.getsockname()[0]
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.dirname(os.path.abspath(APK_PATH)))
    httpd = http.server.ThreadingHTTPServer((me, SERVE_PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://{me}:{SERVE_PORT}/{os.path.basename(APK_PATH)}"

def main():
    if not os.path.exists(APK_PATH):
        print(f"Error: {APK_PATH} not found!", file=sys.stderr)
        return 1
    url = serve()
    print(f"Serving APK at: {url}")
    print(f"Connecting to TV {TV_IP}:{PORT}...")
    sock = socket.create_connection((TV_IP, PORT), timeout=5)
    sock.settimeout(1)
    send(sock, "159>>1>>0")
    path_md5 = hashlib.md5(url.encode()).hexdigest()
    apk_size_mb = str(max(1, os.path.getsize(APK_PATH) // (1024 * 1024)))
    
    cmd = ">>".join(["223", "INSTALL", PACKAGE, LABEL, url, "2", VERSION, apk_size_mb, "", "", "", path_md5])
    print(f"Sending INSTALL command for {LABEL} ({PACKAGE})...")
    send(sock, cmd)

    buf = b""
    last_beat = time.time()
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            pass
        found, buf = messages(buf)
        for msg in found:
            print("TV replied:", msg)
            parts = msg.split(">>")
            if len(parts) < 5 or parts[0] != "223":
                continue
            if parts[1] == "INSTALL":
                if parts[4] == "confirm_pending":
                    print("\n" + "="*60, flush=True)
                    print(">>> [PROMPT] 电视屏幕上已弹出安装确认窗口！请用电视遥控器点击【同意】<<<", flush=True)
                    print("="*60 + "\n", flush=True)
                elif parts[4] == "denied":
                    print("Refused on the TV (用户在电视上拒绝了安装).", file=sys.stderr)
                    return 1
            elif parts[1] == "PROGRESS":
                stage = parts[4]
                percent = parts[5] if len(parts) > 5 else ""
                print(f"Install progress: stage={stage}, percent={percent}")
                if stage == "5":
                    print(f"\nSUCCESS! {LABEL} successfully installed on TV!\n", flush=True)
                    return 0
                if stage == "2":
                    print("The TV could not download or install the APK.", file=sys.stderr)
                    return 1
        if time.time() - last_beat > 5:
            send(sock, "150>>")
            last_beat = time.time()
    sock.close()
    print("Timed out waiting for the TV.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
