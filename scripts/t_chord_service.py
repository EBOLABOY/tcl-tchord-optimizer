#!/usr/bin/env python3
"""
TCL T-Chord Joint Optimizer Service & Home Assistant Bridge (v3.1.0 - PBA)
Monitors TV state via HA WebSocket (with heartbeat), auto-injects verified v3.1
PBA in-RAM profile on power-on via ADB AudioTool, and exposes HTTP API on :8998.
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

state_info: Dict[str, Any] = {
    "version": "3.1.0",
    "profile": "PBA-300Hz-LR4-ICLD-8dB",
    "status": "服务已启动 (待机)",
    "last_injected": "从未",
    "tv_ip": DEFAULT_TV_IP,
    "soundbar_ip": "未知",
    "soundbar_model": "TCL Q95K 11.1.4 (Illusonic DSP Type 13)",
    "latency_policy": "保留原生 Q95K HDMI-CEC 0x1B 出厂协商时延表",
    "crossover": "",
    "icld_offset": "",
    "pba_curve": "",
    "architecture": "Q95K 11.1.4 (22单元+双7吋推挽炮) + 75Q9M Pro 2.1.2 (5单元) 联合 27 单元 T和弦",
}

orchestrator: Optional[TChordOrchestrator] = None
CONFIG: Dict[str, Any] = {}


def refresh_state_from_config():
    if not orchestrator:
        return
    vol_db = orchestrator.get_vol_offset_db()
    vol_tenth = orchestrator.get_vol_offset_tenth_db()
    specs = orchestrator.build_peq_specs()
    hpf_specs = [s for s in specs if s["type"] == 1]

    state_info["version"] = orchestrator.config_data.get("version", "3.1.0")
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


def update_ha_sensor(state_str: str, extra_attrs: Optional[dict] = None):
    token, host, port = CONFIG.get("ha_token"), CONFIG.get("ha_host"), CONFIG.get("ha_port")
    if not token or not host:
        return
    try:
        refresh_state_from_config()
        attrs = {
            "friendly_name": "TCL T和弦声学优化状态",
            "icon": "mdi:speaker-multiple",
            "version": state_info["version"],
            "profile": state_info["profile"],
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
            "disk_safety": "100% 纯内存生效 (断电或 --restore 完整复原)",
        }
        if extra_attrs:
            attrs.update(extra_attrs)
        req = urllib.request.Request(
            f"http://{host}:{port}/api/states/sensor.tcl_tchord_status",
            data=json.dumps({"state": state_str, "attributes": attrs}).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5):
            logger.info(f"Updated HA sensor.tcl_tchord_status -> {state_str}")
    except Exception as e:
        logger.warning(f"Failed to update HA sensor: {e}")


async def perform_injection():
    logger.info("Executing v3.1 PBA T-Chord injection via Orchestrator...")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, orchestrator.apply_profile)
    if success:
        state_info["last_injected"] = ts
        state_info["status"] = "已优化 (v3.1 PBA 生效)"
        state_info["soundbar_ip"] = orchestrator.soundbar_ip or "未连接"
        state_info["soundbar_model"] = getattr(orchestrator, "soundbar_model", state_info["soundbar_model"])
        refresh_state_from_config()
        update_ha_sensor(state_info["status"])
        return {"status": "success", "timestamp": ts, "message": "Verified v3.1 PBA profile applied"}
    state_info["status"] = "注入失败 (请检查电视连接)"
    update_ha_sensor("注入失败")
    return {"status": "error", "timestamp": ts, "message": "Profile injection failed"}


async def handle_inject(request):
    return web.json_response(await perform_injection())


async def handle_restore(request):
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, orchestrator.restore_defaults)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if success:
        state_info["status"] = "已恢复出厂默认"
        update_ha_sensor("已恢复出厂默认")
        return web.json_response({"status": "success", "timestamp": ts, "message": "Restored factory defaults"})
    return web.json_response({"status": "error", "timestamp": ts, "message": "Failed to restore defaults"})


async def handle_status(request):
    refresh_state_from_config()
    return web.json_response(state_info)


async def handle_diagnose(request):
    loop = asyncio.get_event_loop()
    sbar_ok, sbar_ip, sbar_details = await loop.run_in_executor(None, orchestrator.probe_soundbar)
    tv_ok, tv_model = await loop.run_in_executor(None, orchestrator.probe_tv)
    if sbar_ok:
        state_info["soundbar_ip"] = sbar_ip
        state_info["soundbar_model"] = f"TCL {sbar_details.get('model', 'Q95K')} 11.1.4 (Illusonic DSP Type {sbar_details.get('dsp_type', 13)})"
    refresh_state_from_config()
    return web.json_response({
        "tv_online": tv_ok,
        "tv_model": tv_model,
        "soundbar_online": sbar_ok,
        "soundbar_ip": sbar_ip,
        "soundbar_details": sbar_details,
        "current_status": state_info,
    })


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
                    update_ha_sensor(state_info["status"])
                    await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
                    await ws.receive_json()

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data).get("event", {}).get("data", {})
                            if data.get("entity_id") == entity_id:
                                old_s = (data.get("old_state") or {}).get("state")
                                new_s = (data.get("new_state") or {}).get("state")
                                logger.info(f"TV {entity_id}: {old_s} -> {new_s}")
                                if new_s in ("on", "idle", "playing") and old_s in ("off", "standby", "unavailable"):
                                    logger.info("TV powered on! Waiting 4.0s for HAL & CEC stabilization...")
                                    await asyncio.sleep(4.0)
                                    await perform_injection()
                                elif new_s in ("off", "standby"):
                                    state_info["status"] = "待机中 (开机将自动注入)"
                                    update_ha_sensor(state_info["status"])
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as e:
            logger.warning(f"HA WS error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)


def main():
    parser = argparse.ArgumentParser(description="TCL T-Chord Joint Optimizer Service & HA Bridge (v3.1.0)")
    parser.add_argument("--ha-host", default=DEFAULT_HA_HOST)
    parser.add_argument("--ha-port", type=int, default=DEFAULT_HA_PORT)
    parser.add_argument("--ha-token", default=DEFAULT_HA_TOKEN)
    parser.add_argument("--tv-ip", default=DEFAULT_TV_IP)
    parser.add_argument("--soundbar-ip", default=DEFAULT_SOUNDBAR_IP)
    parser.add_argument("--entity-id", default=DEFAULT_HA_ENTITY_ID)
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    args = parser.parse_args()

    CONFIG.update({
        "ha_host": args.ha_host,
        "ha_port": args.ha_port,
        "ha_token": args.ha_token,
        "tv_ip": args.tv_ip,
        "soundbar_ip": args.soundbar_ip,
        "ha_entity_id": args.entity_id,
    })

    global orchestrator
    orchestrator = TChordOrchestrator(tv_ip=args.tv_ip, soundbar_ip=args.soundbar_ip or None)
    state_info["tv_ip"] = args.tv_ip
    refresh_state_from_config()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.router.add_post("/inject", handle_inject)
    app.router.add_post("/restore", handle_restore)
    app.router.add_get("/status", handle_status)
    app.router.add_get("/diagnose", handle_diagnose)
    loop.create_task(ha_ws_monitor())

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", args.port).start())
    logger.info(f"T-Chord Bridge Service v3.1.0 (PBA) listening on :{args.port}")
    loop.run_forever()


if __name__ == "__main__":
    main()
