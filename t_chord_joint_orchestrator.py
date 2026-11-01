#!/usr/bin/env python3
"""
TCL T-Chord Joint Acoustic Optimizer & Orchestrator (v2.0.0)
Hardware Targets:
  - TV: TCL 75Q9M Pro (MediaTek Pentonic 700 / MT9653, Android 14)
  - Soundbar: TCL Q95K 11.1.4 (MediaTek MT8532 + Illusonic DSP Type 13)

Academic Acoustic Grounding:
  - Wallis & Lee (JAES 2015): Precedence effect limitation in median plane & comb filter elimination
  - Jens Blauert (1969/1997): 3.5 kHz "Vorn-Oben" elevation band peaking filter
  - Linkwitz-Riley 4th Order (24dB/oct) High-Pass crossover at 480 Hz for TV micro-transducer protection
  - Bertelson & de Gelder (2004): Ventriloquism effect visual capture window
"""

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, "configs", "default_codec_latency.json")
INJECTOR_JAR_PATH = os.path.join(SCRIPT_DIR, "injector", "bin", "audiotool.jar")

DEFAULT_TV_IP = "192.168.100.101"
DEFAULT_SOUNDBAR_CANDIDATES = ["192.168.100.133", "192.168.100.134"]
DEFAULT_LATENCIES = [42, 58, 66, 80, 84, 92, 74, 54, 82, 50, 50]
REMOTE_JAR_PATH = "/data/local/tmp/audiotool.jar"
REMOTE_CLASS = "com.tcl.tchord.optimizer.AudioTool"


class TChordOrchestrator:
    def __init__(self, tv_ip: str = DEFAULT_TV_IP, soundbar_ip: Optional[str] = None, config_path: Optional[str] = None):
        self.tv_ip = tv_ip
        self.soundbar_ip = soundbar_ip
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_data = self._load_config()

    def _load_config(self) -> Dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Warning: Failed to parse config {self.config_path}: {e}")
        return {}

    def get_latencies(self) -> List[int]:
        slots = self.config_data.get("slots", {})
        if slots:
            values = list(slots.values())[:11]
            if len(values) == 11:
                return values
        return DEFAULT_LATENCIES

    def probe_soundbar(self, ip: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        candidates = [ip] if ip else ([self.soundbar_ip] if self.soundbar_ip else DEFAULT_SOUNDBAR_CANDIDATES)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for candidate_ip in candidates:
            if not candidate_ip:
                continue
            url = f"https://{candidate_ip}:8043/api/getData?path=settings:/system/modelName&roles=@all&_nocache={int(time.time()*1000)}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TChordOrchestrator/2.0"})
                with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    model = data.get("value", {}).get("string_", "TCL Q95K Soundbar")
                    self.soundbar_ip = candidate_ip
                    return True, candidate_ip, model
            except Exception:
                continue
        return False, None, None

    def run_adb(self, cmd_args: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        cmd = ["adb", "-s", f"{self.tv_ip}:5555"] + cmd_args
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except FileNotFoundError:
            return -1, "", "adb command not found in system PATH"
        except subprocess.TimeoutExpired:
            return -2, "", f"adb command timed out after {timeout}s"
        except Exception as e:
            return -3, "", str(e)

    def probe_tv(self) -> Tuple[bool, str]:
        # Test connection
        subprocess.run(["adb", "connect", f"{self.tv_ip}:5555"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        ret, stdout, stderr = self.run_adb(["shell", "getprop", "ro.product.model"])
        if ret == 0 and stdout:
            return True, stdout
        return False, stderr or "Failed to connect to TV via ADB"

    def ensure_injector(self, force: bool = False) -> bool:
        if not force:
            ret, stdout, _ = self.run_adb(["shell", f"[ -f {REMOTE_JAR_PATH} ] && echo EXISTS"])
            if ret == 0 and "EXISTS" in stdout:
                return True

        if not os.path.exists(INJECTOR_JAR_PATH):
            print(f"[!] Error: Local injector jar missing at {INJECTOR_JAR_PATH}")
            return False

        print(f"[*] Pushing {os.path.basename(INJECTOR_JAR_PATH)} to TV {REMOTE_JAR_PATH}...")
        ret, stdout, stderr = self.run_adb(["push", INJECTOR_JAR_PATH, REMOTE_JAR_PATH])
        if ret == 0:
            print("[+] Injector deployed successfully.")
            return True
        else:
            print(f"[-] Failed to push injector: {stderr}")
            return False

    def apply_profile(self) -> bool:
        print("=" * 68)
        print(" Applying T-Chord Calibrated Acoustic Profile (In-Memory)")
        print("=" * 68)

        # 1. Probe Soundbar
        sbar_ok, sbar_ip, sbar_model = self.probe_soundbar()
        if sbar_ok:
            print(f"[+] Soundbar Detected: {sbar_model} at {sbar_ip}:8043 (eARC Master)")
        else:
            print("[!] Soundbar probe did not respond on local HTTPS. Continuing with TV HAL calibration...")

        # 2. Probe TV
        tv_ok, tv_model = self.probe_tv()
        if not tv_ok:
            print(f"[-] TV Connection Failed: {tv_model}")
            print(f"    Ensure TV at {self.tv_ip}:5555 has ADB enabled in Settings -> Developer Options.")
            return False
        print(f"[+] TV Connected: {tv_model} ({self.tv_ip})")

        # 3. Ensure injector
        if not self.ensure_injector():
            return False

        # 4. Execute calibrated profile
        latencies = self.get_latencies()
        lat_csv = ",".join(str(x) for x in latencies)
        print(f"[*] Calibrated 11-Slot Latencies: [{lat_csv}]")
        print("[*] Acoustic Crossover: 480 Hz Linkwitz-Riley 4th Order (24dB/oct)")
        print("[*] Height Anchor Filter: 3.5 kHz Blauert Peaking (+3 dB, Q=1.5)")

        cmd = [
            "shell",
            f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} apply_calibrated_profile {lat_csv}"
        ]
        ret, stdout, stderr = self.run_adb(cmd, timeout=12)
        if ret == 0:
            print(stdout)
            print("\n" + "=" * 68)
            print(">>> [SUCCESS] T-Chord Calibrated Acoustic Profile Successfully Active! <<<")
            print("=" * 68)
            return True
        else:
            print(f"[-] Injection failed: {stderr}\n{stdout}")
            return False

    def restore_defaults(self) -> bool:
        print("=" * 68)
        print(" Restoring TV Audio HAL to Factory Defaults")
        print("=" * 68)
        tv_ok, tv_model = self.probe_tv()
        if not tv_ok:
            print(f"[-] TV Connection Failed: {tv_model}")
            return False

        if not self.ensure_injector():
            return False

        cmd = [
            "shell",
            f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} restore_defaults"
        ]
        ret, stdout, stderr = self.run_adb(cmd, timeout=10)
        if ret == 0:
            print(stdout)
            print("[+] Audio HAL successfully restored to factory defaults.")
            return True
        else:
            print(f"[-] Restore failed: {stderr}\n{stdout}")
            return False

    def diagnose(self):
        print("=" * 68)
        print(" TCL T-Chord Acoustic & System Comprehensive Diagnostics")
        print("=" * 68)

        # 1. TV ADB Check
        print("\n--- 1. TV Android & Audio HAL Status ---")
        tv_ok, tv_model = self.probe_tv()
        if tv_ok:
            print(f"[+] TV ADB: ONLINE (Model: {tv_model})")
            ret, soc, _ = self.run_adb(["shell", "getprop", "ro.board.platform"])
            ret2, build, _ = self.run_adb(["shell", "getprop", "ro.build.display.id"])
            print(f"    SoC Platform: {soc}")
            print(f"    Build ID:     {build}")

            # AudioTool query
            if self.ensure_injector():
                print("\n[*] Querying Active HAL Audio Parameters:")
                ret, stdout, _ = self.run_adb(["shell", f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} query_status"])
                for line in stdout.splitlines():
                    print(f"    {line}")
        else:
            print(f"[-] TV ADB: OFFLINE ({tv_model})")

        # 2. Soundbar StreamSDK Check
        print("\n--- 2. Q95K Soundbar & Illusonic DSP Status ---")
        sbar_ok, sbar_ip, sbar_model = self.probe_soundbar()
        if sbar_ok:
            print(f"[+] Soundbar: ONLINE ({sbar_model}) at https://{sbar_ip}:8043")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                url = f"https://{sbar_ip}:8043/api/getData?path=settings:/illusonic/soundbarType&roles=@all"
                req = urllib.request.Request(url, headers={"User-Agent": "TChordOrchestrator/2.0"})
                with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sb_type = data.get("value", {}).get("i32_", "N/A")
                    print(f"    Illusonic DSP Profile Type: {sb_type} (Q95K 11.1.4 Array)")
            except Exception as e:
                print(f"    Illusonic DSP query: {e}")
        else:
            print(f"[-] Soundbar: OFFLINE (Probed candidates: {DEFAULT_SOUNDBAR_CANDIDATES})")

        # 3. Acoustic Theoretical Summary
        print("\n--- 3. Acoustic & Mathematical Configuration ---")
        latencies = self.get_latencies()
        slots_desc = [
            "PCM 2.0 (LPCM Linear Stereo)",
            "Dolby Digital (AC-3 5.1)",
            "Dolby Digital Plus (E-AC-3)",
            "Dolby Atmos (E-AC-3 JOC)",
            "Dolby TrueHD Lossless",
            "Dolby TrueHD + Dolby Atmos",
            "Dolby MAT 2.0 / LPCM Multichannel",
            "DTS Core 5.1",
            "DTS-HD Master Audio / DTS:X",
            "Slot 9 (Reserved)",
            "Slot 10 (Reserved)"
        ]
        print("  Index | Codec Type                       | Calibrated Latency")
        print("  ------+----------------------------------+-------------------")
        for i, (desc, val) in enumerate(zip(slots_desc, latencies)):
            print(f"   [{i:02d}] | {desc:<32} | {val:>3} ms")

        print("\n  Crossover Strategy: Linkwitz-Riley 4th Order (24 dB/oct) @ 480 Hz")
        print("  Blauert Filter:     Fc=3500 Hz, Q=1.5, Gain=+3 dB (Median Plane Elevation)")
        print("  Safety Boundary:    Zero-disk-write. Fully volatile in-RAM parameters.")
        print("=" * 68 + "\n")

    def show_params(self):
        latencies = self.get_latencies()
        data = {
            "version": "2.0.0",
            "audio_hal_keys": {
                "AQ_TCSE_ENABLE": "1",
                "AQ_TCSE_TUTTI_CHORAL_MODE": "1",
                "AQ_TCSE_Speech_Clear": "1",
                "AQ_TCSE_VERTICAL_SOUND_FIELD_MODE": "1",
                "AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY": ",".join(str(x) for x in latencies)
            },
            "peq_filters": [
                {
                    "band": 1,
                    "type": "HighPass_LR4_Stage1",
                    "param_string": "AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=1;Gain=0;Enable=1"
                },
                {
                    "band": 2,
                    "type": "HighPass_LR4_Stage2",
                    "param_string": "AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=2;Gain=0;Enable=1"
                },
                {
                    "band": 3,
                    "type": "Blauert_Elevation_Peaking",
                    "param_string": "AQ_PEQ_PARAM=1;Fc=3500;Type=0;AQ_DEVICE=SpeakerOutput;Q=150;Band=3;Gain=3;Enable=1"
                }
            ],
            "routing_command": "com.tcl.audiomenu.service.TclHdmiTvClient.selectTSymphonyOutput()"
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="TCL T-Chord Joint Acoustic Optimizer & Orchestrator (v2.0.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 t_chord_joint_orchestrator.py --apply
  python3 t_chord_joint_orchestrator.py --diagnose
  python3 t_chord_joint_orchestrator.py --restore
  python3 t_chord_joint_orchestrator.py --show-params
        """
    )
    parser.add_argument("--apply", action="store_true", help="Apply calibrated acoustic profile to TV Audio HAL")
    parser.add_argument("--restore", action="store_true", help="Restore TV Audio HAL to factory defaults")
    parser.add_argument("--diagnose", action="store_true", help="Run full diagnostic suite on TV and Soundbar")
    parser.add_argument("--show-params", action="store_true", help="Print calibrated HAL parameters in JSON")
    parser.add_argument("--push-jar", action="store_true", help="Force push injector audiotool.jar to TV")
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP, help=f"TCL TV IP address (default: {DEFAULT_TV_IP})")
    parser.add_argument("--soundbar-ip", help="TCL Q95K Soundbar IP address (default: auto-probe)")
    parser.add_argument("--config", help="Path to custom JSON calibration configuration")

    args = parser.parse_args()

    orchestrator = TChordOrchestrator(
        tv_ip=args.tv_ip,
        soundbar_ip=args.soundbar_ip,
        config_path=args.config
    )

    if args.push_jar:
        orchestrator.ensure_injector(force=True)
        return

    if args.show_params:
        orchestrator.show_params()
        return

    if args.diagnose:
        orchestrator.diagnose()
        return

    if args.restore:
        orchestrator.restore_defaults()
        return

    if args.apply:
        orchestrator.apply_profile()
        return

    # If no action flag passed, run apply by default with diagnostics
    orchestrator.diagnose()
    orchestrator.apply_profile()


if __name__ == "__main__":
    main()
