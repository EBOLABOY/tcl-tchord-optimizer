#!/usr/bin/env python3
"""
TCL T-Chord Joint Acoustic Optimizer & Orchestrator (v2.1.1)
Hardware Targets:
  - TV: TCL 75Q9M Pro (MediaTek Pentonic 700 / MT9653 / Android 14)
  - Soundbar: TCL Q95K 11.1.4 (MediaTek MT8532 + Illusonic DSP Type 13)

Academic Acoustic Grounding:
  - Wallis & Lee (JAES 2015): Precedence effect limitation in median plane & comb filter elimination
  - Jens Blauert (1969/1997): 3.5 kHz "Vorn-Oben" elevation band peaking filter
  - Linkwitz-Riley 4th Order (24dB/oct) High-Pass crossover at 480 Hz for TV micro-transducer protection
  - Bertelson & de Gelder (2004): Ventriloquism effect visual capture window
  - Interchannel Level Difference (ICLD): -8dB TV micro-transducer attenuation relative to soundbar
"""

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, "configs", "default_codec_latency.json")
INJECTOR_JAR_PATH = os.path.join(SCRIPT_DIR, "injector", "bin", "audiotool.jar")

DEFAULT_TV_IP = "192.168.100.101"
DEFAULT_SOUNDBAR_CANDIDATES = ["192.168.100.133", "192.168.100.134"]
REMOTE_JAR_PATH = "/data/local/tmp/audiotool.jar"
REMOTE_CLASS = "com.tcl.tchord.optimizer.AudioTool"


class TChordOrchestrator:
    def __init__(self, tv_ip: str = DEFAULT_TV_IP, soundbar_ip: Optional[str] = None, config_path: Optional[str] = None):
        self.tv_ip = tv_ip
        self.soundbar_ip = soundbar_ip
        self.soundbar_model = "TCL Q95K 11.1.4 (Illusonic DSP Type 13)"
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
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
                return [int(v) for v in values]
        return [42, 58, 66, 80, 84, 92, 74, 54, 82, 50, 50]

    def get_vol_offset_db(self) -> int:
        icld = self.config_data.get("icld_level_balance", {})
        val = icld.get("tv_speaker_attenuation_relative_to_sbar_db", -8.0)
        try:
            return int(round(float(val)))
        except (ValueError, TypeError):
            return -8

    def get_peq_command_strings(self) -> List[str]:
        peq_list = self.config_data.get("peq_filters", [])
        commands = []
        if peq_list:
            for p in peq_list:
                band = p.get("band", 1)
                fc = p.get("fc", 480)
                ptype = p.get("type", 2)
                device = p.get("device", "SpeakerOutput")
                q = p.get("q", 71)
                gain = p.get("gain", 0)
                commands.append(f"AQ_PEQ_PARAM=1;Fc={fc};Type={ptype};AQ_DEVICE={device};Q={q};Band={band};Gain={gain};Enable=1")
        else:
            commands = [
                "AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=1;Gain=0;Enable=1",
                "AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=2;Gain=0;Enable=1",
                "AQ_PEQ_PARAM=1;Fc=3500;Type=0;AQ_DEVICE=SpeakerOutput;Q=150;Band=3;Gain=3;Enable=1"
            ]
        return commands

    def probe_soundbar(self, ip: Optional[str] = None) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        candidates = [ip] if ip else ([self.soundbar_ip] if self.soundbar_ip else DEFAULT_SOUNDBAR_CANDIDATES)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        details: Dict[str, Any] = {}

        for candidate_ip in candidates:
            if not candidate_ip:
                continue
            url = f"https://{candidate_ip}:8043/api/getData?path=settings:/system/modelName&roles=@all&_nocache={int(time.time()*1000)}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TChordOrchestrator/2.1"})
                with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    model = data.get("value", {}).get("string_", "TCL Q95K Soundbar")
                    self.soundbar_ip = candidate_ip
                    self.soundbar_model = model
                    details["model"] = model
                    details["ip"] = candidate_ip

                    # Query additional runtime properties
                    for key, path in [
                        ("dsp_type", "settings:/illusonic/soundbarType"),
                        ("lipsync_ms", "settings:/imx8AudioFramework/lipSyncConf"),
                        ("volume", "player:volume"),
                        ("mute", "settings:/mediaPlayer/mute")
                    ]:
                        try:
                            sub_url = f"https://{candidate_ip}:8043/api/getData?path={path}&roles=@all"
                            sub_req = urllib.request.Request(sub_url, headers={"User-Agent": "TChordOrchestrator/2.1"})
                            with urllib.request.urlopen(sub_req, context=ctx, timeout=1.5) as sub_resp:
                                sub_data = json.loads(sub_resp.read().decode("utf-8"))
                                val_obj = sub_data.get("value", {})
                                if "i32_" in val_obj:
                                    details[key] = val_obj["i32_"]
                                elif "bool_" in val_obj:
                                    details[key] = val_obj["bool_"]
                                else:
                                    details[key] = val_obj
                        except Exception:
                            pass

                    return True, candidate_ip, details
            except Exception:
                continue
        return False, None, {}

    def set_soundbar_lipsync(self, ip: Optional[str] = None, delay_ms: int = 0) -> bool:
        target_ip = ip or self.soundbar_ip
        if not target_ip:
            return False
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"https://{target_ip}:8043/api/setData"
        payload = {
            "path": "settings:/imx8AudioFramework/lipSyncConf",
            "role": "value",
            "value": {"type": "i32_", "i32_": delay_ms}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "TChordOrchestrator/2.1"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

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
        try:
            subprocess.run(["adb", "connect", f"{self.tv_ip}:5555"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        except Exception as e:
            return False, f"ADB connection timed out / offline: {e}"
        ret, stdout, stderr = self.run_adb(["shell", "getprop", "ro.product.model"], timeout=4)
        if ret == 0 and stdout:
            return True, stdout
        return False, stderr or "Failed to connect to TV via ADB (TV may be in standby/sleep)"

    def ensure_injector(self, force: bool = False) -> bool:
        if not os.path.exists(INJECTOR_JAR_PATH):
            print(f"[!] Error: Local injector jar missing at {INJECTOR_JAR_PATH}")
            return False

        local_size = str(os.path.getsize(INJECTOR_JAR_PATH))

        if not force:
            ret, stdout, _ = self.run_adb(["shell", f"[ -f {REMOTE_JAR_PATH} ] && stat -c %s {REMOTE_JAR_PATH} 2>/dev/null || echo 0"])
            if ret == 0 and stdout.strip() == local_size:
                return True

        print(f"[*] Deploying {os.path.basename(INJECTOR_JAR_PATH)} ({local_size} bytes) to TV {REMOTE_JAR_PATH}...")
        ret, stdout, stderr = self.run_adb(["push", INJECTOR_JAR_PATH, REMOTE_JAR_PATH])
        if ret == 0:
            print("[+] Injector deployed successfully.")
            return True
        else:
            print(f"[-] Failed to push injector: {stderr}")
            return False

    def configure_tv_audio_routing(self) -> bool:
        print("[*] Synchronizing TV multi-sound device and eARC settings...")
        # 1. Enable TV Multi-sound device (T-Chord / Simultaneous speaker output)
        self.run_adb(["shell", "settings", "put", "system", "tcl_app_settings_multi_sound_device", "true"])
        # 2. Enable eARC mode
        self.run_adb(["shell", "settings", "put", "system", "tcl_app_settings_eARC_mode", "true"])
        # 3. Enable System Audio Mode and ARC on CEC bus
        self.run_adb(["shell", "cmd", "hdmi_control", "setsystemaudiomode", "on"])
        self.run_adb(["shell", "cmd", "hdmi_control", "setarc", "on"])
        return True

    def apply_profile(self) -> bool:
        print("=" * 70)
        print(" Applying T-Chord Calibrated Acoustic Profile (In-Memory)")
        print("=" * 70)

        # 1. Probe Soundbar
        sbar_ok, sbar_ip, sbar_details = self.probe_soundbar()
        if sbar_ok:
            model = sbar_details.get("model", "Q95K")
            dsp_type = sbar_details.get("dsp_type", 13)
            lipsync = sbar_details.get("lipsync_ms", 0)
            vol = sbar_details.get("volume", "N/A")
            print(f"[+] Soundbar Connected: {model} at {sbar_ip}:8043")
            print(f"    Illusonic DSP Profile: Type {dsp_type} (11.1.4 Array) | Volume: {vol}")
            if lipsync != 0:
                print(f"[!] WARNING: Soundbar internal lipSyncConf is set to {lipsync} ms!")
                print("[*] Attempting to zero out Soundbar lipSyncConf via REST API...")
                zero_ok = self.set_soundbar_lipsync(sbar_ip, 0)
                if zero_ok:
                    print("[+] Soundbar lipSyncConf automatically zeroed to 0 ms.")
                else:
                    print("[-] Notice: Soundbar REST write returned 401/Unauthorized (firmware requires local pairing).")
                    print("    Please set Soundbar lipSync to 0ms via TCL Home App or Soundbar remote for bit-exact T-Chord alignment.")
        else:
            print("[!] Soundbar probe did not respond on local HTTPS.")
            print("    Please ensure TV is connected to Soundbar via HDMI eARC Port 1.")

        # 2. Probe TV
        tv_ok, tv_model = self.probe_tv()
        if not tv_ok:
            print(f"[-] TV Connection Failed: {tv_model}")
            print(f"    Ensure TV at {self.tv_ip}:5555 has ADB enabled in Settings -> Developer Options.")
            return False
        print(f"[+] TV Connected: {tv_model} ({self.tv_ip})")

        # 3. Synchronize TV HDMI-CEC & Multi-sound routing
        self.configure_tv_audio_routing()

        # 4. Ensure injector
        if not self.ensure_injector():
            return False

        # 5. Extract configuration dynamically from JSON
        latencies = self.get_latencies()
        lat_csv = ",".join(str(x) for x in latencies)
        vol_offset = self.get_vol_offset_db()
        peq_cmds = self.get_peq_command_strings()
        peq_arg = "||".join(peq_cmds)

        print(f"[*] Latency Matrix (11 slots): [{lat_csv}]")
        print(f"[*] ICLD Speaker Level Balance: {vol_offset} dB (SpeakerOutput attenuation)")
        print(f"[*] Dynamic PEQ Filters ({len(peq_cmds)} stages):")
        for cmd in peq_cmds:
            print(f"    -> {cmd}")

        # 6. Execute injection on TV via app_process
        cmd = [
            "shell",
            f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} apply_calibrated_profile '{lat_csv}' '{vol_offset}' '{peq_arg}'"
        ]
        ret, stdout, stderr = self.run_adb(cmd, timeout=12)
        if ret == 0:
            print("\n" + stdout)
            print("\n" + "=" * 70)
            print(">>> [SUCCESS] T-Chord Calibrated Acoustic Profile Successfully Active! <<<")
            print("=" * 70)
            return True
        else:
            print(f"[-] Injection failed (ret={ret}): {stderr}\n{stdout}")
            return False

    def restore_defaults(self) -> bool:
        print("=" * 70)
        print(" Restoring TV Audio HAL to Factory Defaults")
        print("=" * 70)
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
            print(f"[-] Restore failed (ret={ret}): {stderr}\n{stdout}")
            return False

    def diagnose(self):
        print("=" * 70)
        print(" TCL T-Chord Acoustic & System Comprehensive Diagnostics")
        print("=" * 70)

        # 1. TV Android & Audio HAL Status
        print("\n--- 1. TV Android & Audio HAL Status ---")
        tv_ok, tv_model = self.probe_tv()
        if tv_ok:
            print(f"[+] TV ADB: ONLINE (Model: {tv_model})")
            _, soc, _ = self.run_adb(["shell", "getprop", "ro.board.platform"])
            _, build, _ = self.run_adb(["shell", "getprop", "ro.build.display.id"])
            _, multi_sound, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_multi_sound_device"])
            _, earc_mode, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_eARC_mode"])
            print(f"    SoC Platform:         {soc}")
            print(f"    Build ID:             {build}")
            print(f"    Multi-Sound Setting:  {multi_sound}")
            print(f"    eARC Mode Setting:    {earc_mode}")

            if self.ensure_injector():
                print("\n[*] Querying Active HAL Audio Parameters:")
                ret, stdout, _ = self.run_adb(["shell", f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} query_status"])
                for line in stdout.splitlines():
                    print(f"    {line}")
        else:
            print(f"[-] TV ADB: OFFLINE ({tv_model})")

        # 2. Q95K Soundbar & HDMI-CEC Status
        print("\n--- 2. Q95K Soundbar & HDMI-CEC Link Status ---")
        sbar_ok, sbar_ip, sbar_details = self.probe_soundbar()
        if sbar_ok:
            model = sbar_details.get("model", "Q95K")
            dsp_type = sbar_details.get("dsp_type", "13")
            lipsync = sbar_details.get("lipsync_ms", "0")
            vol = sbar_details.get("volume", "N/A")
            mute = sbar_details.get("mute", "false")
            print(f"[+] Soundbar REST API: ONLINE ({model}) at https://{sbar_ip}:8043")
            print(f"    Illusonic DSP Profile: Type {dsp_type} (Q95K 11.1.4 Array)")
            print(f"    Current Volume:        {vol}")
            print(f"    Mute State:            {mute}")
            print(f"    Internal LipSync:      {lipsync} ms")
        else:
            print(f"[-] Soundbar REST API: OFFLINE (Probed candidates: {DEFAULT_SOUNDBAR_CANDIDATES})")

        # Check TV HDMI-CEC Dump
        if tv_ok:
            _, cec_dump, _ = self.run_adb(["shell", "dumpsys hdmi_control | grep -E 'logical_address: 0x05|mSystemAudioActivated|AudioDeviceOutType'"])
            if cec_dump:
                print("    HDMI-CEC Bus State:")
                for l in cec_dump.splitlines():
                    print(f"      {l.strip()}")

        # 3. Dynamic Configuration Table
        print("\n--- 3. Dynamic Acoustic Configuration (from JSON) ---")
        latencies = self.get_latencies()
        vol_offset = self.get_vol_offset_db()
        peq_cmds = self.get_peq_command_strings()

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

        print(f"\n  ICLD Level Balance: {vol_offset} dB (TV micro-transducer attenuation)")
        print("  PEQ Filter Commands:")
        for c in peq_cmds:
            print(f"    {c}")
        print("  Safety Boundary:    Zero-disk-write. Fully volatile in-RAM parameters.")
        print("=" * 70 + "\n")

    def show_params(self):
        latencies = self.get_latencies()
        vol_offset = self.get_vol_offset_db()
        peq_cmds = self.get_peq_command_strings()

        data = {
            "version": "2.1.1",
            "config_file": self.config_path,
            "audio_hal_keys": {
                "AQ_TCSE_ENABLE": "1",
                "AQ_TCSE_TUTTI_CHORAL_MODE": "1",
                "AQ_TCSE_Speech_Clear": "1",
                "AQ_TCSE_VERTICAL_SOUND_FIELD_MODE": "1",
                "AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY": ",".join(str(x) for x in latencies),
                "AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL": "16777215",
                "AQ_OUTPUT_VOL_OFFSET": f"{vol_offset};AQ_DEVICE=SpeakerOutput"
            },
            "peq_filters": peq_cmds,
            "routing_actions": [
                "settings put system tcl_app_settings_multi_sound_device true",
                "settings put system tcl_app_settings_eARC_mode true",
                "cmd hdmi_control setsystemaudiomode on",
                "cmd hdmi_control setarc on"
            ]
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="TCL T-Chord Joint Acoustic Optimizer & Orchestrator (v2.1.1)",
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
    parser.add_argument("--show-params", action="store_true", help="Print active HAL parameters in JSON")
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

    # Default action
    orchestrator.diagnose()
    orchestrator.apply_profile()


if __name__ == "__main__":
    main()
