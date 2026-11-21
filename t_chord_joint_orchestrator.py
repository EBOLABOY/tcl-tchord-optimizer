#!/usr/bin/env python3
"""
TCL T-Chord Joint Acoustic Optimizer & Orchestrator (v3.1.0 - PBA)
Binary-verified In-RAM Perceptual Band Allocation (PBA) calibration for
TCL 75Q9M Pro (MT9655) + TCL Q95K (11.1.4 / Illusonic DSP Type 13).
"""

import argparse
import json
import os
import re
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

# Verified libmi3_audio_hal.so biquard_config Type enum
PEQ_TYPE_MAP = {
    "peaking": 0,
    "hpf": 1,
    "highpass": 1,
    "lpf": 2,
    "lowpass": 2,
    "low_shelf": 3,
    "lowshelf": 3,
    "high_shelf": 4,
    "highshelf": 4,
}
PEQ_TYPE_NAMES = {0: "Peaking", 1: "HPF", 2: "LPF", 3: "LowShelf", 4: "HighShelf"}

# Verified audio.tcl.default.so _fpi_audio_convert_sbar_format (0x290e0)
CEC_SBAR_FORMAT_LABELS = {
    1: "PCM",
    2: "DD (AC-3)",
    3: "DDP (E-AC-3)",
    4: "DDP Atmos",
    5: "TrueHD",
    6: "TrueHD Atmos",
    7: "MAT",
    8: "MAT Atmos",
    9: "DTS Core",
    10: "DTS-HD",
    11: "DTS:X / MA",
}


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

    def get_vol_offset_db(self) -> float:
        icld = self.config_data.get("icld_level_balance", {})
        try:
            return float(icld.get("tv_speaker_attenuation_db", -8.0))
        except (ValueError, TypeError):
            return -8.0

    def get_vol_offset_tenth_db(self) -> int:
        """Convert dB float to MediaTek MI3 APAF 0.1 dB integer unit (-1200..+120)."""
        return max(-1200, min(120, int(round(self.get_vol_offset_db() * 10.0))))

    def build_peq_specs(self) -> List[Dict[str, Any]]:
        """Parse PEQ filters from JSON and convert human dB/Q units to verified MI3 HAL integers."""
        peq_list = self.config_data.get("peq_filters") or [
            {"band": 9, "device": "SpeakerOutput", "type": "hpf", "fc_hz": 300, "q_factor": 0.71, "gain_db": 0.0, "enable": True},
            {"band": 10, "device": "SpeakerOutput", "type": "hpf", "fc_hz": 300, "q_factor": 0.71, "gain_db": 0.0, "enable": True},
            {"band": 11, "device": "SpeakerOutput", "type": "peaking", "fc_hz": 1000, "q_factor": 1.0, "gain_db": -2.0, "enable": True},
            {"band": 12, "device": "SpeakerOutput", "type": "peaking", "fc_hz": 4000, "q_factor": 1.4, "gain_db": 2.0, "enable": True},
            {"band": 13, "device": "SpeakerOutput", "type": "peaking", "fc_hz": 8000, "q_factor": 1.4, "gain_db": 1.5, "enable": True},
        ]

        specs = []
        for p in peq_list:
            band = int(p.get("band", 9))
            if not (1 <= band <= 13):
                raise ValueError(f"Invalid PEQ band {band}: MI3 HAL supports Band 1..13")
            device = str(p.get("device", "SpeakerOutput"))
            raw_type = p.get("type", "hpf")
            ptype = PEQ_TYPE_MAP[raw_type.strip().lower()] if isinstance(raw_type, str) else int(raw_type)
            fc_hz = int(round(float(p.get("fc_hz", 300))))
            enable = 1 if p.get("enable", True) else 0
            gain_db = float(p.get("gain_db", 0.0))
            gain_hal = max(-180, min(180, int(round(gain_db * 10.0))))

            q_factor = float(p.get("q_factor", 0.71 if ptype != 0 else 1.4))
            q_hal = max(5, min(160, int(round(q_factor * 10.0)))) if ptype == 0 else max(50, min(90, int(round(q_factor * 100.0))))

            specs.append({
                "band": band,
                "device": device,
                "type": ptype,
                "type_name": PEQ_TYPE_NAMES.get(ptype, str(ptype)),
                "fc_hz": fc_hz,
                "q_factor": q_factor,
                "q_hal": q_hal,
                "gain_db": gain_db,
                "gain_hal": gain_hal,
                "enable": enable,
                "description": p.get("description", ""),
                "cmd": f"AQ_PEQ_PARAM=1;Fc={fc_hz};Type={ptype};AQ_DEVICE={device};Q={q_hal};Band={band};Gain={gain_hal};Enable={enable}",
            })
        return specs

    def get_extra_hal_commands(self) -> List[str]:
        flags = self.config_data.get("hal_flags", {})
        cmds: List[str] = []
        if flags.get("dolby_dialog_enhancer_enable", False):
            lvl = max(0, min(10, int(flags.get("dolby_dialog_enhancer_level", 0))))
            cmds.append(f"AQ_DolbyDialogEnhancerEnable=On;AQ_DolbyDialogEnhancer={lvl}")
        else:
            cmds.append("AQ_DolbyDialogEnhancerEnable=Off")
        cmds.append("AQ_DolbyVolumeLevler=On" if flags.get("dolby_volume_leveler", False) else "AQ_DolbyVolumeLevler=Off")
        return cmds

    def probe_soundbar(self, ip: Optional[str] = None) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Read-only StreamSDK CM API telemetry probe (respects authMode=setData)."""
        candidates = [ip] if ip else ([self.soundbar_ip] if self.soundbar_ip else DEFAULT_SOUNDBAR_CANDIDATES)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        def _fetch(base_ip: str, path: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
            url = f"https://{base_ip}:8043/api/getData?path={path}&roles=@all&_nocache={int(time.time()*1000)}"
            req = urllib.request.Request(url, headers={"User-Agent": "TChordOrchestrator/3.1"})
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        for candidate_ip in candidates:
            if not candidate_ip:
                continue
            try:
                data = _fetch(candidate_ip, "settings:/system/modelName", timeout=2.5)
                if not data:
                    continue
                model = data.get("value", {}).get("string_", "Q95K")
                self.soundbar_ip = candidate_ip
                self.soundbar_model = f"TCL {model} 11.1.4 (Illusonic DSP)"
                details: Dict[str, Any] = {"model": model, "ip": candidate_ip}

                for key, path in [
                    ("firmware_version", "settings:/version"),
                    ("dsp_type", "settings:/illusonic/soundbarType"),
                    ("dsp_config", "settings:/illusonic/initialConfigName"),
                    ("lipsync_ms", "settings:/imx8AudioFramework/lipSyncConf"),
                    ("audio_output_delay", "settings:/system/audioOutputDelay"),
                    ("cec_enabled", "settings:/imx8AudioFramework/cecEnabled"),
                    ("volume", "player:volume"),
                    ("attenuation_db", "settings:/mediaPlayer/attenuation"),
                    ("mute", "settings:/mediaPlayer/mute"),
                    ("equalizer_on", "settings:/mediaPlayer/equalizerOnOff"),
                    ("postprocessing", "settings:/mediaPlayer/postprocessing"),
                    ("bass", "settings:/mediaPlayer/bass"),
                    ("treble", "settings:/mediaPlayer/treble"),
                    ("loudness", "settings:/mediaPlayer/loudness"),
                    ("power_target", "powermanager:target"),
                    ("auth_mode", "settings:/webserver/authMode"),
                ]:
                    try:
                        val_obj = (_fetch(candidate_ip, path, timeout=1.5) or {}).get("value", {})
                        for vt in ("i32_", "bool_", "string_", "double_", "webserverAuthMode"):
                            if vt in val_obj:
                                details[key] = val_obj[vt]
                                break
                        else:
                            if "powerTarget" in val_obj:
                                details[key] = val_obj["powerTarget"].get("target", "unknown")
                            elif "systemAudioDelay" in val_obj:
                                arr = val_obj["systemAudioDelay"]
                                details[key] = arr[0].get("delayUs", 0) if arr else 0
                    except Exception:
                        pass

                return True, candidate_ip, details
            except Exception:
                continue
        return False, None, {}

    def run_adb(self, cmd_args: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        try:
            p = subprocess.run(
                ["adb", "-s", f"{self.tv_ip}:5555"] + cmd_args,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
            )
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        except FileNotFoundError:
            return -1, "", "adb not found in PATH"
        except subprocess.TimeoutExpired:
            return -2, "", f"adb timed out after {timeout}s"
        except Exception as e:
            return -3, "", str(e)

    def probe_tv(self) -> Tuple[bool, str]:
        try:
            subprocess.run(["adb", "connect", f"{self.tv_ip}:5555"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        except Exception as e:
            return False, f"ADB connect error: {e}"
        ret, stdout, stderr = self.run_adb(["shell", "getprop", "ro.product.model"], timeout=4)
        return (True, stdout) if (ret == 0 and stdout) else (False, stderr or "TV ADB offline")

    def ensure_injector(self, force: bool = False) -> bool:
        if not os.path.exists(INJECTOR_JAR_PATH):
            print(f"[!] Missing injector jar: {INJECTOR_JAR_PATH}")
            return False
        local_size = str(os.path.getsize(INJECTOR_JAR_PATH))
        if not force:
            ret, stdout, _ = self.run_adb(["shell", f"[ -f {REMOTE_JAR_PATH} ] && stat -c %s {REMOTE_JAR_PATH} 2>/dev/null || echo 0"])
            if ret == 0 and stdout.strip() == local_size:
                return True
        print(f"[*] Deploying audiotool.jar ({local_size} bytes) -> {REMOTE_JAR_PATH}...")
        ret, _, stderr = self.run_adb(["push", INJECTOR_JAR_PATH, REMOTE_JAR_PATH])
        if ret != 0:
            print(f"[-] Push failed: {stderr}")
            return False
        return True

    @staticmethod
    def decode_packed_sbar_latency(raw_val: str) -> str:
        try:
            u32 = int(raw_val.strip()) & 0xFFFFFFFF
            fmt1, lat1 = (u32 >> 28) & 0xF, (u32 >> 16) & 0xFFF
            fmt2, lat2 = (u32 >> 12) & 0xF, u32 & 0xFFF
            parts = []
            if fmt1 or lat1:
                parts.append(f"{CEC_SBAR_FORMAT_LABELS.get(fmt1, f'fmt#{fmt1}')}={lat1}ms")
            if fmt2 or lat2:
                parts.append(f"{CEC_SBAR_FORMAT_LABELS.get(fmt2, f'fmt#{fmt2}')}={lat2}ms")
            return f"0x{u32:08X} ({', '.join(parts) if parts else 'empty'})"
        except Exception:
            return raw_val

    def ensure_tv_routing(self):
        if not self.config_data.get("tv_routing", {}).get("ensure_multi_sound_and_earc", True):
            return
        _, multi, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_multi_sound_device"])
        _, earc, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_eARC_mode"])
        if multi.strip().lower() != "true":
            self.run_adb(["shell", "settings", "put", "system", "tcl_app_settings_multi_sound_device", "true"])
        if earc.strip().lower() != "true":
            self.run_adb(["shell", "settings", "put", "system", "tcl_app_settings_eARC_mode", "true"])

    def get_tv_runtime_state(self) -> Dict[str, Any]:
        """Single fast ADB round-trip (~150ms) to read TV power, T-Chord mode, audio route, PIDs & active stream."""
        state: Dict[str, Any] = {
            "tv_online": False,
            "wakefulness": "Unknown",
            "is_awake": False,
            "last_wake_time": "",
            "audioserver_pid": "",
            "hal_pid": "",
            "tsymphony_prop": "",
            "tsymphony_setting": "",
            "multi_sound": "",
            "earc_mode": "",
            "music_volume": None,
            "music_devices": "",
            "active_stream": "Standby",
            "is_tchord_active": False,
            "has_speaker_route": False,
            "has_arc_route": False,
            "fingerprint": "",
        }
        try:
            subprocess.run(["adb", "connect", f"{self.tv_ip}:5555"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        except Exception:
            return state

        probe_cmd = (
            "echo WAKE=$(dumpsys power | grep -m1 'mWakefulness=' | sed 's/.*mWakefulness=//'); "
            "echo LASTWAKE=$(dumpsys power | grep -m1 'mLastWakeTime=' | awk '{print $1}' | sed 's/.*=//'); "
            "echo AS_PID=$(pidof audioserver); "
            "echo HAL_PID=$(pidof vendor.mediatek.hardware.audio.service); "
            "echo TSYMP_PROP=$(getprop sys.tcl.tsymphony.mode); "
            "echo TSYMP_SET=$(settings get global tcl_app_settings_tsymphony_mode); "
            "echo MULTI=$(settings get system tcl_app_settings_multi_sound_device); "
            "echo EARC=$(settings get system tcl_app_settings_eARC_mode); "
            "dumpsys audio | awk '/^- STREAM_MUSIC:/{f=1;next} f && /streamVolume:/{print \"VOL=\"$0} f && /Devices:/{print \"DEVS=\"$0; exit}'; "
            "dumpsys media.audio_flinger | awk '/^Output thread /{out=1;t=$3;act=0} /^Input thread /{out=0;act=0} out && /Standby: no/{act=1;fmt=\"\";sr=\"\"} act && /HAL format:/{fmt=$0} act && /Sample rate:/{sr=$0} act && /Channel count:/{ch=$0; print \"STREAM=\"t\"|\"fmt\"|\"sr\"|\"ch; act=0}'"
        )
        ret, out, _ = self.run_adb(["shell", probe_cmd], timeout=6)
        if ret != 0 or not out:
            return state

        state["tv_online"] = True
        active_streams: List[str] = []
        for raw_line in out.splitlines():
            line = raw_line.strip()
            if line.startswith("WAKE="):
                state["wakefulness"] = line.split("=", 1)[1].strip()
            elif line.startswith("LASTWAKE="):
                state["last_wake_time"] = line.split("=", 1)[1].strip()
            elif line.startswith("AS_PID="):
                state["audioserver_pid"] = line.split("=", 1)[1].strip()
            elif line.startswith("HAL_PID="):
                state["hal_pid"] = line.split("=", 1)[1].strip()
            elif line.startswith("TSYMP_PROP="):
                state["tsymphony_prop"] = line.split("=", 1)[1].strip()
            elif line.startswith("TSYMP_SET="):
                state["tsymphony_setting"] = line.split("=", 1)[1].strip()
            elif line.startswith("MULTI="):
                state["multi_sound"] = line.split("=", 1)[1].strip().lower()
            elif line.startswith("EARC="):
                state["earc_mode"] = line.split("=", 1)[1].strip().lower()
            elif line.startswith("VOL="):
                m = re.search(r"streamVolume:(\d+)", line)
                if m:
                    state["music_volume"] = int(m.group(1))
            elif line.startswith("DEVS="):
                m = re.search(r"Devices:\s*(.+)$", line)
                if m:
                    state["music_devices"] = m.group(1).strip()
            elif line.startswith("STREAM="):
                body = line.split("=", 1)[1]
                fmt_m = re.search(r"\((AUDIO_FORMAT_[^)]+)\)", body)
                sr_m = re.search(r"Sample rate:\s*(\d+)\s*Hz", body)
                ch_m = re.search(r"Channel count:\s*(\d+)", body)
                if fmt_m:
                    fmt = fmt_m.group(1).replace("AUDIO_FORMAT_", "")
                    sr = f"{int(sr_m.group(1))//1000}kHz" if sr_m else ""
                    ch = f"{ch_m.group(1)}ch" if ch_m else ""
                    active_streams.append(" ".join(p for p in (fmt, sr, ch) if p))

        devs_l = state["music_devices"].lower()
        state["is_awake"] = state["wakefulness"] == "Awake"
        state["has_speaker_route"] = "speaker" in devs_l
        state["has_arc_route"] = ("hdmi_arc" in devs_l) or ("hdmi_earc" in devs_l)
        state["is_tchord_active"] = (
            state["tsymphony_prop"] == "1"
            and state["has_speaker_route"]
            and (state["has_arc_route"] or state["multi_sound"] == "true")
        )
        if active_streams:
            state["active_stream"] = " + ".join(dict.fromkeys(active_streams))
        state["fingerprint"] = f"{state['last_wake_time']}:{state['audioserver_pid']}:{state['hal_pid']}"
        return state

    def verify_hal_in_logcat(self, expected_vol_tenth: int, expected_peqs: List[Dict[str, Any]], since_ts: Optional[str] = None) -> Tuple[bool, List[str], Dict[str, Any]]:
        _, hal_pid, _ = self.run_adb(["shell", "pidof", "vendor.mediatek.hardware.audio.service"], timeout=4)
        hal_pid = hal_pid.strip().split()[0] if hal_pid.strip() else ""
        if hal_pid.isdigit():
            _, log_out, _ = self.run_adb(["shell", "logcat", "-d", "-v", "threadtime", f"--pid={hal_pid}", "-t", "300"], timeout=6)
        else:
            _, log_out, _ = self.run_adb(["shell", "logcat", "-d", "-v", "threadtime", "-t", "500"], timeout=6)

        lines = log_out.splitlines()
        if since_ts:
            lines = [l for l in lines if len(l) >= 18 and l[:18] >= since_ts]

        report: List[str] = []
        meta: Dict[str, Any] = {"vol_step": None, "peq_count": 0, "error_count": 0}
        all_ok = True

        vol_pat = re.compile(r"_MI_LAPAF_FILTER_VOLUME_SetAudioVolParam.*Set VolGain\(step\):(-?\d+).*SPEAKER")
        vol_matches = [m for l in lines if (m := vol_pat.search(l))]
        if vol_matches:
            step = int(vol_matches[-1].group(1))
            meta["vol_step"] = step
            report.append(f"[PASS] <APAF> SPEAKER VolGain(step)={step} ({step/10.0:.1f} dB) with OutputVolumeOffset={expected_vol_tenth} ({expected_vol_tenth/10.0:+.1f} dB)")
        else:
            report.append(f"[INFO] <APAF> SPEAKER VolGain unchanged (OutputVolumeOffset={expected_vol_tenth} already active in DSP)")

        peq_hits = [l for l in lines if "setPeqParam: Speaker_MsePeq set peqparam" in l]
        meta["peq_count"] = len(peq_hits)
        if len(peq_hits) >= len(expected_peqs):
            report.append(f"[PASS] Speaker_MsePeq accepted {len(peq_hits)}/{len(expected_peqs)} PEQ updates on immune Band {[s['band'] for s in expected_peqs]}")
        else:
            all_ok = False
            report.append(f"[WARN] Expected {len(expected_peqs)} Speaker_MsePeq updates, observed {len(peq_hits)}")

        err_keys = ("Failed to set PEQ", "Out of max PEQ", "SetParameter fail", "Set customer parameter fail", "Invalid band", "Error Invalid pipelinename")
        err_hits = [l for l in lines if any(k in l for k in err_keys)]
        meta["error_count"] = len(err_hits)
        if err_hits:
            all_ok = False
            for eh in err_hits[-5:]:
                report.append(f"[FAIL] HAL error: {eh.strip()}")
        else:
            report.append("[PASS] Zero MI3 / APAF / audio_hw_primary errors detected")

        return all_ok, report, meta

    def apply_profile(self) -> bool:
        print("=" * 74)
        print(" Applying TCL T-Chord v3.1 Perceptual Band Allocation (PBA) Profile")
        print("=" * 74)

        sbar_ok, sbar_ip, d = self.probe_soundbar()
        if sbar_ok:
            print(f"[+] Soundbar: TCL {d.get('model','Q95K')} @ https://{sbar_ip}:8043 | DSP Type {d.get('dsp_type',13)} | Vol {d.get('volume')} ({d.get('attenuation_db')} dB) | LipSync {d.get('lipsync_ms')} ms")
            if isinstance(d.get("lipsync_ms"), int) and d["lipsync_ms"] != 0:
                print(f"[!] ADVISORY: Soundbar lipSyncConf={d['lipsync_ms']} ms. Set Audio Delay to 0 ms in TCL Home App / remote.")
        else:
            print("[!] Soundbar StreamSDK offline (continuing TV-side calibration).")

        tv_ok, tv_model = self.probe_tv()
        if not tv_ok:
            print(f"[-] TV ADB offline: {tv_model}")
            return False
        print(f"[+] TV: {tv_model} ({self.tv_ip}:5555)")

        self.ensure_tv_routing()
        if not self.ensure_injector():
            return False

        vol_db = self.get_vol_offset_db()
        vol_tenth = self.get_vol_offset_tenth_db()
        peq_specs = self.build_peq_specs()
        extra_cmds = self.get_extra_hal_commands()

        print(f"[*] T-Chord CEC Link   : Native Q95K 0xA0/0x1B latency & channel preserved")
        print(f"[*] Base ICLD Offset   : {vol_db:+.1f} dB -> OutputVolumeOffset={vol_tenth}")
        print(f"[*] PBA Immune PEQ     : {len(peq_specs)} bands on Band {[s['band'] for s in peq_specs]}")
        for s in peq_specs:
            net_db = vol_db + s["gain_db"]
            print(f"    Band {s['band']:2d} [{s['type_name']:<8s}] Fc={s['fc_hz']:4d}Hz  Q={s['q_factor']:.2f} (HAL {s['q_hal']:2d})  Gain={s['gain_db']:+.1f}dB (net {net_db:+.1f}dB)")

        _, tv_ts, _ = self.run_adb(["shell", "date '+%m-%d %H:%M:%S.000'"], timeout=4)
        since_ts = tv_ts.strip() if tv_ts and len(tv_ts.strip()) >= 14 else None

        peq_arg = "||".join(s["cmd"] for s in peq_specs)
        extra_arg = "||".join(extra_cmds)
        ret, stdout, stderr = self.run_adb(
            ["shell", f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} apply_calibrated_profile '{vol_tenth}' '{peq_arg}' '{extra_arg}'"],
            timeout=12,
        )
        if ret != 0:
            print(f"[-] AudioTool failed (ret={ret}): {stderr}\n{stdout}")
            return False
        print("\n" + stdout)

        time.sleep(0.3)
        verified, v_lines, v_meta = self.verify_hal_in_logcat(vol_tenth, peq_specs, since_ts=since_ts)
        self.last_verify_meta = {**v_meta, "verified": verified, "report": v_lines}
        print("\n--- Live TV Audio HAL / MI3 DSP Verification (logcat) ---")
        for vl in v_lines:
            print(f"  {vl}")
        print("=" * 74)
        print(">>> [VERIFIED SUCCESS] v3.1 PBA Profile Active in DSP! <<<" if verified else "[!] Dispatched with verification warnings.")
        print("=" * 74)
        return verified

    def restore_defaults(self, reset_legacy_v2_settings: bool = True) -> bool:
        print("=" * 74)
        print(" Restoring TV Audio HAL & Settings to Clean Factory Defaults")
        print("=" * 74)
        tv_ok, tv_model = self.probe_tv()
        if not tv_ok:
            print(f"[-] TV ADB offline: {tv_model}")
            return False
        if not self.ensure_injector():
            return False

        ret, stdout, stderr = self.run_adb(
            ["shell", f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} restore_defaults"],
            timeout=10,
        )
        if ret != 0:
            print(f"[-] Restore failed (ret={ret}): {stderr}\n{stdout}")
            return False
        print(stdout)

        if reset_legacy_v2_settings:
            for ns, key, val in [
                ("system", "tcl_sys_audio_channel_center", "0"),
                ("system", "tcl_sys_audio_channel_top", "0"),
                ("system", "tcl_sys_audio_vertical_sound_field", "0"),
                ("global", "tcl_app_settings_ai_audio_visual", "true"),
            ]:
                self.run_adb(["shell", "settings", "put", ns, key, val])
        print("[+] TV Audio HAL & settings cleanly restored.")
        return True

    def diagnose(self):
        print("=" * 74)
        print(" TCL T-Chord v3.1 Diagnostics (TV HAL + HDMI-CEC TRD + Q95K StreamSDK)")
        print("=" * 74)

        tv_ok, tv_model = self.probe_tv()
        if tv_ok:
            _, soc, _ = self.run_adb(["shell", "getprop", "ro.board.platform"])
            _, build, _ = self.run_adb(["shell", "getprop", "ro.build.display.id"])
            _, tsymp, _ = self.run_adb(["shell", "getprop", "sys.tcl.tsymphony.mode"])
            _, multi, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_multi_sound_device"])
            _, earc, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_app_settings_eARC_mode"])
            _, opt_lat, _ = self.run_adb(["shell", "settings", "get", "system", "tcl_sys_audio_system_option_type_16393"])
            print(f"\n[TV] {tv_model} ({self.tv_ip}:5555) | SoC={soc} | Build={build}")
            print(f"     T-Symphony={tsymp} | MultiSound={multi} | eARC={earc}")
            print(f"     Last CEC 0x1B Latency (0x4009): {self.decode_packed_sbar_latency(opt_lat)}")

            if self.ensure_injector():
                print("\n[Q95K via TV HDMI-CEC TclHdmiTvClient / TRD]")
                _, cec_out, _ = self.run_adb(["shell", f"CLASSPATH={REMOTE_JAR_PATH} app_process / {REMOTE_CLASS} query_soundbar_cec"], timeout=8)
                for line in cec_out.splitlines():
                    print(f"     {line}")
        else:
            print(f"\n[TV] OFFLINE ({tv_model})")

        sbar_ok, sbar_ip, d = self.probe_soundbar()
        if sbar_ok:
            print(f"\n[Q95K via StreamSDK :8043 Read-Only] https://{sbar_ip}:8043")
            print(f"     Model={d.get('model')} | FW={d.get('firmware_version')} | Illusonic Type={d.get('dsp_type')} ({d.get('dsp_config')})")
            print(f"     Vol={d.get('volume')} ({d.get('attenuation_db')} dB) | Mute={d.get('mute')} | LipSync={d.get('lipsync_ms')}ms | OutDelay={d.get('audio_output_delay')}us")
            print(f"     EQ={d.get('equalizer_on')} | PostProc={d.get('postprocessing')} | Bass={d.get('bass')} | Treble={d.get('treble')} | Loudness={d.get('loudness')}")
            print(f"     Power={d.get('power_target')} | CEC={d.get('cec_enabled')} | AuthMode={d.get('auth_mode')}")
        else:
            print(f"\n[Q95K] StreamSDK OFFLINE (probed {DEFAULT_SOUNDBAR_CANDIDATES})")

        print("\n[Active v3.1 PBA Calibration Profile]")
        vol_db, vol_tenth = self.get_vol_offset_db(), self.get_vol_offset_tenth_db()
        print(f"     ICLD Offset: {vol_db:+.1f} dB -> AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset={vol_tenth};AQ_DEVICE=SpeakerOutput")
        for s in self.build_peq_specs():
            print(f"     Band {s['band']:2d} | {s['type_name']:<8s} | Fc={s['fc_hz']:4d}Hz | Q={s['q_factor']:.2f} (HAL {s['q_hal']:2d}) | Gain={s['gain_db']:+.1f}dB (net {vol_db+s['gain_db']:+.1f}dB)")
        print("=" * 74)

    def live_check(self) -> Dict[str, Any]:
        """Read-only live runtime & HAL pipeline analysis."""
        st = self.get_tv_runtime_state()
        sbar_ok, sbar_ip, sbar_d = self.probe_soundbar()
        hal_events: Dict[str, Any] = {"last_vol_step": None, "last_sbar_latency": None, "aiaq_events": 0, "hal_errors": 0}

        if st["tv_online"] and st["hal_pid"].isdigit():
            _, log_out, _ = self.run_adb(["shell", "logcat", "-d", "-v", "threadtime", f"--pid={st['hal_pid']}", "-t", "500"], timeout=6)
            vol_pat = re.compile(r"Set VolGain\(step\):(-?\d+).*SPEAKER")
            lat_pat = re.compile(r"_utils_lapaf_get_tcse_tutti_choral_latency:\s*(.+)$")
            for line in log_out.splitlines():
                if (m := vol_pat.search(line)):
                    hal_events["last_vol_step"] = int(m.group(1))
                if (m := lat_pat.search(line)):
                    hal_events["last_sbar_latency"] = m.group(1).strip()
                if "TRACK_AIAQ_MODE" in line or "setDolbySoundMode" in line:
                    hal_events["aiaq_events"] += 1
                if any(k in line for k in ("Failed to set PEQ", "Out of max PEQ", "SetParameter fail", "Invalid band")):
                    hal_events["hal_errors"] += 1

        result = {"tv_state": st, "soundbar_online": sbar_ok, "soundbar_ip": sbar_ip, "soundbar": sbar_d, "hal_recent": hal_events}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    def show_params(self):
        vol_db, vol_tenth = self.get_vol_offset_db(), self.get_vol_offset_tenth_db()
        peq_specs = self.build_peq_specs()
        print(json.dumps({
            "version": self.config_data.get("version", "3.1.0"),
            "profile": self.config_data.get("profile_name", "PBA-300Hz-LR4-ICLD-8dB"),
            "icld_db": vol_db,
            "audio_hal_commands": [
                "AQ_TCSE_Speech_Clear=0",
                f"AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset={vol_tenth};AQ_DEVICE=SpeakerOutput",
            ] + [s["cmd"] for s in peq_specs] + self.get_extra_hal_commands(),
        }, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="TCL T-Chord Joint Acoustic Optimizer (v3.1.0 - PBA)")
    parser.add_argument("--apply", action="store_true", help="Apply v3.1 PBA profile and verify in TV logcat")
    parser.add_argument("--restore", action="store_true", help="Restore TV Audio HAL and legacy settings to defaults")
    parser.add_argument("--diagnose", action="store_true", help="Run TV HAL, HDMI-CEC TRD, and Q95K StreamSDK diagnostics")
    parser.add_argument("--check", action="store_true", help="Fast live runtime & T-Chord state check (JSON)")
    parser.add_argument("--show-params", action="store_true", help="Print resolved HAL parameter commands in JSON")
    parser.add_argument("--push-jar", action="store_true", help="Force push audiotool.jar to TV")
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP, help=f"TCL TV IP (default: {DEFAULT_TV_IP})")
    parser.add_argument("--soundbar-ip", help="TCL Q95K IP (default: auto-probe)")
    parser.add_argument("--config", help="Custom JSON calibration profile path")
    args = parser.parse_args()

    orch = TChordOrchestrator(tv_ip=args.tv_ip, soundbar_ip=args.soundbar_ip, config_path=args.config)
    if args.push_jar:
        orch.ensure_injector(force=True)
    elif args.show_params:
        orch.show_params()
    elif args.diagnose:
        orch.diagnose()
    elif args.check:
        orch.live_check()
    elif args.restore:
        sys.exit(0 if orch.restore_defaults() else 1)
    elif args.apply:
        sys.exit(0 if orch.apply_profile() else 1)
    else:
        orch.diagnose()
        sys.exit(0 if orch.apply_profile() else 1)


if __name__ == "__main__":
    main()
