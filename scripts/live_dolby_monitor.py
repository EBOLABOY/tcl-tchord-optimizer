#!/usr/bin/env python3
"""
TCL T-Chord v3.1 Live Audio Pipeline & HAL Diagnostics Monitor
Monitors real-time MediaTek MI_APAF / Audio HAL, Q95K HDMI-CEC TRD state,
and StreamSDK telemetry during live playback.
"""

import os
import re
import select
import subprocess
import sys
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

from t_chord_joint_orchestrator import TChordOrchestrator

TV_IP = os.environ.get("TV_IP", "192.168.100.101")
SOUNDBAR_IP = os.environ.get("SOUNDBAR_IP", "192.168.100.133")


def print_header(title: str):
    print("\n" + "=" * 76)
    print(f" {title}")
    print("=" * 76)


def analyze_audio_flinger(dump_text: str):
    info = {"active_threads": []}
    for block in dump_text.split("Output thread"):
        if not block.strip() or "name AudioOut" not in block:
            continue
        lines = block.splitlines()
        thread_name = lines[0].strip().split(",")[0] if lines else "Unknown"
        is_standby = "Standby: yes" in block
        fmt_m = re.search(r"HAL format:\s+(0x[0-9a-fA-F]+)\s+\(([^)]+)\)", block)
        rate_m = re.search(r"Sample rate:\s+(\d+)\s+Hz", block)
        ch_m = re.search(r"Channel count:\s+(\d+)", block)
        mask_m = re.search(r"Channel mask:\s+(0x[0-9a-fA-F]+)\s+\(([^)]+)\)", block)
        info["active_threads"].append({
            "name": thread_name,
            "standby": is_standby,
            "format": fmt_m.group(2) if fmt_m else "PCM_16_BIT",
            "sample_rate": rate_m.group(1) if rate_m else "48000",
            "channels": ch_m.group(1) if ch_m else "2",
            "channel_mask": mask_m.group(2) if mask_m else "stereo",
        })
    return info


def start_capture(duration_sec: int = 20):
    print_header(f"LIVE HAL CAPTURE ({duration_sec}s Window - Read-Only, No Logcat Clear)")
    logcat_cmd = [
        "adb", "-s", f"{TV_IP}:5555", "shell", "logcat", "-v", "time", "-T", "1",
        "audio_hw_primary:V", "APAF:V", "MI_AUDIO:V", "thal_audio:V", "TclSoundEffect:V", "*:S"
    ]
    proc = subprocess.Popen(logcat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start_time = time.time()
    events = []
    keywords = [
        "VolGain(step)", "Speaker_MsePeq", "PEQ band", "VolumeOffset", "AQ Volume Index",
        "TuttiChoral", "sbar", "latency", "Dap", "setAiaq", "aiaq", "MAT", "TRUEHD", "E_AC3", "DTS", "eARC"
    ]
    try:
        while time.time() - start_time < duration_sec:
            r, _, _ = select.select([proc.stdout], [], [], 0.5)
            if r:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if any(k.lower() in line.lower() for k in keywords):
                    print(f"  {line}")
                    events.append(line)
    except KeyboardInterrupt:
        print("\n[*] Capture stopped by user.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
    return events


def main():
    orch = TChordOrchestrator(tv_ip=TV_IP, soundbar_ip=SOUNDBAR_IP)
    tv_ok, tv_model = orch.probe_tv()
    sbar_ok, sbar_ip, sbar_details = orch.probe_soundbar()
    print(f"TV ADB ({TV_IP}:5555):        {'[ONLINE] ' + tv_model if tv_ok else '[OFFLINE]'}")
    print(f"Q95K ({SOUNDBAR_IP}:8043):    {'[ONLINE] ' + str(sbar_details.get('model')) if sbar_ok else '[OFFLINE]'}")
    if not tv_ok:
        sys.exit(1)

    duration = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 20
    events = start_capture(duration_sec=duration)

    print_header("OBSERVED PIPELINE SUMMARY")
    print(f"Relevant HAL events captured: {len(events)}")
    _, af_dump, _ = orch.run_adb(["shell", "dumpsys", "media.audio_flinger"], timeout=6)
    for t in analyze_audio_flinger(af_dump).get("active_threads", []):
        st = "ACTIVE" if not t["standby"] else "STANDBY"
        print(f"  Thread {t['name']}: [{st}] {t['format']} {t['sample_rate']}Hz {t['channels']}ch ({t['channel_mask']})")

    if sbar_ok:
        print(f"  Q95K StreamSDK: Vol={sbar_details.get('volume')} ({sbar_details.get('attenuation_db')} dB), "
              f"LipSync={sbar_details.get('lipsync_ms')}ms, DSP=Type {sbar_details.get('dsp_type')}")


if __name__ == "__main__":
    main()
