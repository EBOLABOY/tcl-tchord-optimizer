#!/usr/bin/env python3
"""
TCL T-Chord Joint Optimizer Service & Home Assistant Bridge (v3.1.1 - PVE Guardian)
Dual-trigger state machine (HA WebSocket + periodic TV/T-Chord runtime guardian):
  - Auto-applies v3.1 PBA profile ONLY when TV is Awake AND T-Chord mode is active
  - Auto-reapplies after STR wake-up (mLastWakeTime change) or audioserver/HAL restart
  - Auto-restores full-range 0 dB when switching out of T-Chord (e.g., standalone TV Speaker)
  - Exposes HTTP control & telemetry API on :8998 and syncs Home Assistant sensor.tcl_tchord_status
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import urllib.request
from typing import Any, Dict, Optional
from aiohttp import web

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

from t_chord_joint_orchestrator import TChordOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TChordService")

DEFAULT_HA_HOST = os.environ.get("HA_HOST", "127.0.0.1")
DEFAULT_HA_PORT = int(os.environ.get("HA_PORT", 8123))
DEFAULT_HA_TOKEN = os.environ.get("HA_TOKEN", "")
DEFAULT_TV_IP = os.environ.get("TV_IP", "192.168.100.101")
DEFAULT_SOUNDBAR_IP = os.environ.get("SOUNDBAR_IP", "")
DEFAULT_HA_ENTITY_ID = os.environ.get("HA_ENTITY_ID", "media_player.ke_ting_dian_shi")
DEFAULT_HTTP_PORT = int(os.environ.get("SERVICE_PORT", 8998))
DEFAULT_POLL_INTERVAL = int(os.environ.get("GUARDIAN_POLL_SEC", 15))

state_info: Dict[str, Any] = {
    "version": "3.1.1",
    "profile": "PBA-300Hz-LR4-ICLD-8dB",
    "status": "服务已启动 (初始化检测中)",
    "guardian_mode": "init",
    "last_injected": "从未",
    "last_checked": "从未",
    "tv_ip": DEFAULT_TV_IP,
    "tv_online": False,
    "tv_awake": False,
    "tchord_active": False,
    "audio_route": "未知",
    "active_stream": "未知",
    "music_volume": None,
    "dsp_vol_step": None,
    "dsp_verified": False,
    "soundbar_ip": "未知",
    "soundbar_model": "TCL Q95K 11.1.4 (Illusonic DSP Type 13)",
    "latency_policy": "保留原生 Q95K HDMI-CEC 0x1B 出厂协商时延表",
    "crossover": "",
    "icld_offset": "",
    "pba_curve": "",
    "guardian_poll_sec": DEFAULT_POLL_INTERVAL,
    "architecture": "Q95K 11.1.4 (22单元+双7吋推挽炮) + 75Q9M Pro 2.1.2 (5单元) 联合 27 单元 T和弦",
}

guardian_runtime: Dict[str, Any] = {
    "applied_fingerprint": None,
    "manual_restore_fingerprint": None,
    "last_ha_state": None,
    "last_error_log_ts": 0.0,
}

orchestrator: Optional[TChordOrchestrator] = None
CONFIG: Dict[str, Any] = {}
reconcile_lock: Optional[asyncio.Lock] = None


def refresh_state_from_config():
    if not orchestrator:
        return
    vol_db = orchestrator.get_vol_offset_db()
    vol_tenth = orchestrator.get_vol_offset_tenth_db()
    specs = orchestrator.build_peq_specs()
    hpf_specs = [s for s in specs if s["type"] == 1]

    state_info["profile"] = orchestrator.config_data.get("profile_name", "PBA-300Hz-LR4-ICLD-8dB")
    state_info["icld_offset"] = f"{vol_db:+.1f} dB (OutputVolumeOffset={vol_tenth})"
    if hpf_specs:
        bands = "/".join(str(s["band"]) for s in hpf_specs)
        state_info["crossover"] = f"{hpf_specs[0]['fc_hz']} Hz LR{len(hpf_specs)*2} 真高通 (Type=1, Band {bands})"
    else:
        state_info["crossover"] = "未启用"

    state_info["pba_curve"] = ", ".join(
        f"B{s['band']}:{s['type_name']}@{s['fc_hz']}Hz({s['gain_db']:+.1f}dB,Q={s['q_factor']:.2f})"
        for s in specs
    )


def update_ha_sensor(state_str: str, force: bool = False):
    token, host, port = CONFIG.get("ha_token"), CONFIG.get("ha_host"), CONFIG.get("ha_port")
    if not token or not host:
        return
    if not force and guardian_runtime["last_ha_state"] == (
        state_str,
        state_info["tchord_active"],
        state_info["active_stream"],
        state_info["dsp_vol_step"],
        state_info["last_injected"],
    ):
        return
    try:
        refresh_state_from_config()
        attrs = {
            "friendly_name": "TCL T和弦声学优化状态",
            "icon": "mdi:speaker-multiple" if state_info["tchord_active"] else "mdi:television",
            "version": state_info["version"],
            "profile": state_info["profile"],
            "guardian_mode": state_info["guardian_mode"],
            "tv_online": state_info["tv_online"],
            "tv_awake": state_info["tv_awake"],
            "tchord_active": state_info["tchord_active"],
            "audio_route": state_info["audio_route"],
            "active_stream": state_info["active_stream"],
            "music_volume": state_info["music_volume"],
            "dsp_vol_step": state_info["dsp_vol_step"],
            "dsp_verified": state_info["dsp_verified"],
            "tv_model": "TCL 75Q9M Pro (MT9655 / Onkyo 2.1.2 5单元)",
            "soundbar_model": state_info["soundbar_model"],
            "tv_ip": CONFIG.get("tv_ip"),
            "soundbar_ip": state_info["soundbar_ip"],
            "architecture": state_info["architecture"],
            "latency_policy": state_info["latency_policy"],
            "crossover_frequency": state_info["crossover"],
            "icld_level_balance": state_info["icld_offset"],
            "pba_curve": state_info["pba_curve"],
            "aiaq_immunity": "Speaker_MsePeq Band 9..13 (TCL AIAQ/音效模式仅写 Band 1..8)",
            "last_injected_time": state_info["last_injected"],
            "last_checked_time": state_info["last_checked"],
            "disk_safety": "100% 纯内存生效 (断电或 --restore 完整复原)",
        }
        req = urllib.request.Request(
            f"http://{host}:{port}/api/states/sensor.tcl_tchord_status",
            data=json.dumps({"state": state_str, "attributes": attrs}).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5):
            guardian_runtime["last_ha_state"] = (
                state_str,
                state_info["tchord_active"],
                state_info["active_stream"],
                state_info["dsp_vol_step"],
                state_info["last_injected"],
            )
            logger.info(f"Updated HA sensor.tcl_tchord_status -> {state_str}")
    except Exception as e:
        logger.warning(f"Failed to update HA sensor: {e}")


async def _apply_now(fingerprint: Optional[str] = None, reason: str = "manual") -> Dict[str, Any]:
    logger.info(f"Executing v3.1 PBA T-Chord injection (reason={reason})...")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, orchestrator.apply_profile)
    vmeta = getattr(orchestrator, "last_verify_meta", {}) or {}

    if success:
        state_info["last_injected"] = ts
        state_info["status"] = "已优化 (v3.1 PBA 生效)"
        state_info["guardian_mode"] = "tchord_optimized"
        state_info["dsp_verified"] = bool(vmeta.get("verified", True))
        if vmeta.get("vol_step") is not None:
            state_info["dsp_vol_step"] = vmeta["vol_step"]
        state_info["soundbar_ip"] = orchestrator.soundbar_ip or state_info["soundbar_ip"]
        state_info["soundbar_model"] = getattr(orchestrator, "soundbar_model", state_info["soundbar_model"])
        guardian_runtime["applied_fingerprint"] = fingerprint
        guardian_runtime["manual_restore_fingerprint"] = None
        refresh_state_from_config()
        update_ha_sensor(state_info["status"], force=True)
        return {"status": "success", "timestamp": ts, "dsp_meta": vmeta, "message": "Verified v3.1 PBA profile applied"}

    state_info["status"] = "注入失败 (请检查电视连接)"
    state_info["dsp_verified"] = False
    update_ha_sensor(state_info["status"], force=True)
    return {"status": "error", "timestamp": ts, "dsp_meta": vmeta, "message": "Profile injection failed"}


async def _restore_now(reason: str = "manual", reset_legacy: bool = True, mark_manual_pause: bool = False) -> Dict[str, Any]:
    logger.info(f"Restoring TV Audio HAL to full-range defaults (reason={reason})...")
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, orchestrator.restore_defaults, reset_legacy)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if success:
        state_info["dsp_verified"] = False
        state_info["dsp_vol_step"] = None
        guardian_runtime["applied_fingerprint"] = None
        if mark_manual_pause:
            rt = await loop.run_in_executor(None, orchestrator.get_tv_runtime_state)
            guardian_runtime["manual_restore_fingerprint"] = rt.get("fingerprint") or "manual"
            state_info["guardian_mode"] = "manual_restored"
            state_info["status"] = "已恢复出厂默认 (手动对比)"
        else:
            state_info["guardian_mode"] = "non_tchord_restored"
            state_info["status"] = "非T和弦模式 (已自动还原电视全频)"
        update_ha_sensor(state_info["status"], force=True)
        return {"status": "success", "timestamp": ts, "message": "Restored factory defaults"}
    return {"status": "error", "timestamp": ts, "message": "Failed to restore defaults"}


async def reconcile_tv_state(reason: str = "poll", force_apply: bool = False) -> Dict[str, Any]:
    """Core PVE Guardian state machine: ensures PBA runs iff TV is Awake AND T-Chord is active."""
    async with reconcile_lock:
        loop = asyncio.get_event_loop()
        rt = await loop.run_in_executor(None, orchestrator.get_tv_runtime_state)
        state_info["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
        state_info["tv_online"] = rt["tv_online"]
        state_info["tv_awake"] = rt["is_awake"]
        state_info["tchord_active"] = rt["is_tchord_active"]
        state_info["audio_route"] = rt["music_devices"] or "未知"
        state_info["active_stream"] = rt["active_stream"]
        state_info["music_volume"] = rt["music_volume"]

        if not rt["tv_online"]:
            guardian_runtime["applied_fingerprint"] = None
            guardian_runtime["manual_restore_fingerprint"] = None
            state_info["guardian_mode"] = "tv_offline"
            state_info["status"] = "电视离线 / 待机 (等待唤醒)"
            now = time.time()
            if now - guardian_runtime["last_error_log_ts"] > 120:
                logger.info(f"[{reason}] TV ADB offline/unreachable ({CONFIG.get('tv_ip')}:5555).")
                guardian_runtime["last_error_log_ts"] = now
            update_ha_sensor(state_info["status"])
            return {"action": "offline", "runtime": rt}

        if not rt["is_awake"]:
            guardian_runtime["applied_fingerprint"] = None
            guardian_runtime["manual_restore_fingerprint"] = None
            state_info["guardian_mode"] = "tv_standby"
            state_info["status"] = "待机中 (开机+T和弦将自动注入)"
            update_ha_sensor(state_info["status"])
            return {"action": "standby", "runtime": rt}

        fp = rt["fingerprint"]

        # Case A: TV Awake + T-Chord Active
        if rt["is_tchord_active"]:
            if not force_apply and guardian_runtime["manual_restore_fingerprint"] == fp:
                state_info["guardian_mode"] = "manual_restored"
                state_info["status"] = "已恢复出厂默认 (手动对比)"
                update_ha_sensor(state_info["status"])
                return {"action": "manual_pause", "runtime": rt}

            if force_apply or guardian_runtime["applied_fingerprint"] != fp or state_info["guardian_mode"] != "tchord_optimized":
                logger.info(
                    f"[{reason}] TV Awake + T-Chord Active (route={rt['music_devices']}, stream={rt['active_stream']}, fp={fp}) -> Applying v3.1 PBA"
                )
                res = await _apply_now(fingerprint=fp, reason=reason)
                return {"action": "applied", "result": res, "runtime": rt}

            # Already active on current wake/HAL session
            update_ha_sensor(state_info["status"])
            return {"action": "already_active", "runtime": rt}

        # Case B: TV Awake, NOT in T-Chord Mode (e.g., standalone TV Speaker or Soundbar-only)
        if state_info["guardian_mode"] == "tchord_optimized" or guardian_runtime["applied_fingerprint"] is not None:
            logger.info(
                f"[{reason}] T-Chord exited (tsymphony={rt['tsymphony_prop']}, route={rt['music_devices']}) -> Auto-restoring TV Speaker full-range"
            )
            res = await _restore_now(reason=f"tchord_exit:{reason}", reset_legacy=False, mark_manual_pause=False)
            return {"action": "auto_restored", "result": res, "runtime": rt}

        state_info["guardian_mode"] = "non_tchord_standby"
        state_info["status"] = "待命中 (当前非T和弦模式)"
        update_ha_sensor(state_info["status"])
        return {"action": "non_tchord_noop", "runtime": rt}


async def handle_inject(request):
    async with reconcile_lock:
        loop = asyncio.get_event_loop()
        rt = await loop.run_in_executor(None, orchestrator.get_tv_runtime_state)
        state_info["tv_online"] = rt["tv_online"]
        state_info["tv_awake"] = rt["is_awake"]
        state_info["tchord_active"] = rt["is_tchord_active"]
        state_info["audio_route"] = rt["music_devices"] or "未知"
        state_info["active_stream"] = rt["active_stream"]
        state_info["music_volume"] = rt["music_volume"]
        return web.json_response(await _apply_now(fingerprint=rt.get("fingerprint"), reason="http_inject"))


async def handle_restore(request):
    async with reconcile_lock:
        return web.json_response(await _restore_now(reason="http_restore", reset_legacy=True, mark_manual_pause=True))


async def handle_status(request):
    refresh_state_from_config()
    return web.json_response(state_info)


async def handle_check(request):
    res = await reconcile_tv_state(reason="http_check", force_apply=False)
    refresh_state_from_config()
    return web.json_response({"reconcile": res, "status": state_info})


async def handle_diagnose(request):
    loop = asyncio.get_event_loop()
    rt = await loop.run_in_executor(None, orchestrator.get_tv_runtime_state)
    sbar_ok, sbar_ip, sbar_details = await loop.run_in_executor(None, orchestrator.probe_soundbar)
    if sbar_ok:
        state_info["soundbar_ip"] = sbar_ip
        state_info["soundbar_model"] = f"TCL {sbar_details.get('model', 'Q95K')} 11.1.4 (Illusonic DSP Type {sbar_details.get('dsp_type', 13)})"
    refresh_state_from_config()
    return web.json_response({
        "tv_runtime": rt,
        "soundbar_online": sbar_ok,
        "soundbar_ip": sbar_ip,
        "soundbar_details": sbar_details,
        "current_status": state_info,
    })


async def guardian_poll_loop():
    """Authoritative periodic TV + T-Chord guardian loop."""
    poll_sec = max(5, int(CONFIG.get("poll_interval", DEFAULT_POLL_INTERVAL)))
    logger.info(f"PVE T-Chord Guardian active (interval={poll_sec}s): Awake + T-Chord dual verification enabled.")
    # Immediate startup reconciliation
    try:
        await reconcile_tv_state(reason="startup")
    except Exception as e:
        logger.warning(f"Startup reconcile error: {e}")

    while True:
        await asyncio.sleep(poll_sec)
        try:
            await reconcile_tv_state(reason="guardian_poll")
        except Exception as e:
            logger.warning(f"Guardian poll error: {e}")


async def ha_ws_monitor():
    token, host, port, entity_id = CONFIG.get("ha_token"), CONFIG.get("ha_host"), CONFIG.get("ha_port"), CONFIG.get("ha_entity_id")
    if not token or not host:
        logger.info("HA WebSocket monitor disabled (no HA_TOKEN / HA_HOST).")
        return

    import aiohttp
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"ws://{host}:{port}/api/websocket", timeout=10, heartbeat=30) as ws:
                    await ws.receive_json()
                    await ws.send_json({"type": "auth", "access_token": token})
                    auth_resp = await ws.receive_json()
                    if auth_resp.get("type") != "auth_ok":
                        logger.error(f"HA WS auth failed: {auth_resp}")
                        await asyncio.sleep(10)
                        continue
                    logger.info(f"Connected to HA WebSocket! Listening for {entity_id}...")
                    await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
                    await ws.receive_json()

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data).get("event", {}).get("data", {})
                            if data.get("entity_id") == entity_id:
                                old_s = (data.get("old_state") or {}).get("state")
                                new_s = (data.get("new_state") or {}).get("state")
                                logger.info(f"HA Event {entity_id}: {old_s} -> {new_s}")
                                if new_s in ("on", "idle", "playing") and old_s in ("off", "standby", "unavailable"):
                                    logger.info("HA TV power-on detected! Waiting 4.0s for CEC & T-Chord handshake...")
                                    await asyncio.sleep(4.0)
                                    await reconcile_tv_state(reason="ha_power_on")
                                elif new_s in ("off", "standby"):
                                    await reconcile_tv_state(reason="ha_standby")
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            logger.warning(f"HA WS error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)


def main():
    parser = argparse.ArgumentParser(description="TCL T-Chord Joint Optimizer Service & PVE Guardian (v3.1.1)")
    parser.add_argument("--ha-host", default=DEFAULT_HA_HOST)
    parser.add_argument("--ha-port", type=int, default=DEFAULT_HA_PORT)
    parser.add_argument("--ha-token", default=DEFAULT_HA_TOKEN)
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP)
    parser.add_argument("--soundbar-ip", default=DEFAULT_SOUNDBAR_IP)
    parser.add_argument("--entity-id", default=DEFAULT_HA_ENTITY_ID)
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL)
    args = parser.parse_args()

    CONFIG.update({
        "ha_host": args.ha_host,
        "ha_port": args.ha_port,
        "ha_token": args.ha_token,
        "tv_ip": args.tv_ip,
        "soundbar_ip": args.soundbar_ip,
        "ha_entity_id": args.entity_id,
        "poll_interval": args.poll_interval,
    })

    global orchestrator, reconcile_lock
    orchestrator = TChordOrchestrator(tv_ip=args.tv_ip, soundbar_ip=args.soundbar_ip or None)
    state_info["tv_ip"] = args.tv_ip
    state_info["guardian_poll_sec"] = args.poll_interval
    refresh_state_from_config()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    reconcile_lock = asyncio.Lock()

    app = web.Application()
    app.router.add_post("/inject", handle_inject)
    app.router.add_post("/restore", handle_restore)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/check", handle_check)
    app.router.add_post("/check", handle_check)
    app.router.add_get("/diagnose", handle_diagnose)

    loop.create_task(guardian_poll_loop())
    loop.create_task(ha_ws_monitor())

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", args.port).start())
    logger.info(f"T-Chord PVE Guardian Service v3.1.1 (PBA) listening on :{args.port}")
    loop.run_forever()


if __name__ == "__main__":
    main()
