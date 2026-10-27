#!/usr/bin/env python3
"""
TCL T-Chord Joint Acoustic Optimizer & Native Orchestrator
Collaborative optimization engine for TCL 75Q9M Pro & TCL Q95K Soundbar
"""
import argparse
import json
import os
import ssl
import sys
import urllib.request

DEFAULT_SOUNDBAR_IP = "192.168.100.134"
DEFAULT_TV_IP = "192.168.100.101"

# Default 11-slot codec latency table (in milliseconds)
DEFAULT_LATENCIES = [48, 65, 72, 85, 90, 98, 80, 60, 88, 50, 50]
DEFAULT_CHANNEL_MASK = 1048571  # 0xffffb (pass all channels to sbar except elevated center)
DEFAULT_VERTICAL_PARAMS = "elevation_gain=3dB,crossover_hz=350,hrtf_enable=1"

def check_soundbar(ip):
    print(f"[*] Probing Q95K Soundbar at https://{ip}:8043...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    url = f"https://{ip}:8043/api/getData?path=settings:/system/modelName&roles=@all&_nocache=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            val = data.get("value", {}).get("string_", "Unknown")
            print(f"[+] Soundbar connected! Model: {val}")
            return True
    except Exception as e:
        print(f"[-] Could not connect to Soundbar at {ip}: {e}")
        return False

def generate_injection_params(latencies=None, channel_mask=None, vertical_params=None):
    if latencies is None:
        latencies = DEFAULT_LATENCIES
    if channel_mask is None:
        channel_mask = DEFAULT_CHANNEL_MASK
    if vertical_params is None:
        vertical_params = DEFAULT_VERTICAL_PARAMS

    latency_str = ",".join(str(x) for x in latencies)
    return {
        "AQ_TCSE_TUTTI_CHORAL_MODE": "1",
        "AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY": latency_str,
        "AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL": str(channel_mask),
        "AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS": vertical_params
    }

def print_manual_instructions(params):
    print("\n" + "=" * 65)
    print(" >>> TCL T-CHORD NATIVE AUDIO HAL INJECTION INSTRUCTIONS <<<")
    print("=" * 65)
    print("In your TV's root/user shell or inside an Android Application Context:")
    print("\n  [Java / AudioManager.setParameters]")
    for k, v in params.items():
        print(f'  audioManager.setParameters("{k}={v}");')
    print("\n  [Shell / dumpsys / toybox command]")
    print('  # Or invoke via the companion TChordInjector APK.')
    print("=" * 65 + "\n")

def main():
    parser = argparse.ArgumentParser(description="TCL T-Chord Joint Acoustic Optimizer")
    parser.add_argument("--soundbar-ip", default=DEFAULT_SOUNDBAR_IP, help="Soundbar IP address")
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP, help="TV IP address")
    parser.add_argument("--config", help="Path to custom JSON calibration configuration")
    parser.add_argument("--show-params", action="store_true", help="Print HAL parameters and exit")
    args = parser.parse_args()

    latencies = DEFAULT_LATENCIES
    channel_mask = DEFAULT_CHANNEL_MASK
    vertical_params = DEFAULT_VERTICAL_PARAMS

    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)
            slots = cfg.get("slots", {})
            if slots:
                latencies = list(slots.values())[:11]
            channel_mask = cfg.get("channel_mask", {}).get("decimal", DEFAULT_CHANNEL_MASK)
            v_cfg = cfg.get("vertical_sound_field", {})
            if v_cfg:
                vertical_params = f"elevation_gain={v_cfg.get('elevation_gain_db', 3)}dB,crossover_hz={v_cfg.get('crossover_highpass_hz', 350)},hrtf_enable=1"

    params = generate_injection_params(latencies, channel_mask, vertical_params)

    if args.show_params:
        print(json.dumps(params, indent=2))
        return

    print("=" * 65)
    print(" TCL 75Q9M Pro & Q95K T-Chord Joint Acoustic Optimizer")
    print("=" * 65)
    check_soundbar(args.soundbar_ip)
    print_manual_instructions(params)

if __name__ == "__main__":
    main()
