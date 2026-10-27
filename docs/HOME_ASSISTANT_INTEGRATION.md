# Home Assistant 自动化与状态监控集成指南

本项目提供了与 **Home Assistant (HAOS / Supervised / Container)** 的全自动联动方案，实现：
1. **开机自愈（Zero-Touch Auto-Injection）**：实时监听电视状态变化，开机 3 秒内自动向 MediaTek Audio HAL 注入精准时延与分频参数。
2. **仪表盘状态感知（Live UI Status Monitoring）**：通过 Mushroom 仪表盘卡片实时展现优化生效状态、11 种音频格式时延、350Hz 高通分频与人声抬升指标。
3. **一键重新校准（Manual One-Tap Recalibration）**：可在 HA 仪表盘上一键触发重新注入。

---

## 架构拓扑

```
+-------------------------------------------------------+
| Home Assistant Dashboard (Lovelace UI)               |
| - sensor.tcl_tchord_status: 已优化 (校准生效)         |
| - button.tcl_the_xian_sheng_xue_zhong_xin_xiao_zhun   |
+--------------------------+----------------------------+
                           | Tap Button / REST Action
                           v
+-------------------------------------------------------+
| t_chord_service (Systemd daemon on Proxmox/Linux Host)|
| - HTTP Port 8998: POST /inject, GET /status           |
| - WebSocket Client: 实时监听 media_player.ke_ting_... |
+-------------+-----------------------------+-----------+
              |                             |
      T-Cast Port 6553              HTTPS Port 8043
              v                             v
+---------------------------+ +-------------------------+
| TCL 75Q9M Pro TV          | | TCL Q95K Flagship       |
| MediaTek MT9653 (Android) | | Soundbar (11.1.4 DSP)   |
| Audio HAL In-RAM Tuned    | | Baseline Latency: 0ms   |
+---------------------------+ +-------------------------+
```

---

## 1. 部署后台守护进程 (`t_chord_service.py`)

在局域网内任意常开 Linux 主机（如 Proxmox VE、软路由、树莓派或 NAS）上运行：

```bash
# 复制脚本到 /root 或部署目录
cp scripts/t_chord_service.py /root/t_chord_service.py

# 注册为 systemd 系统服务
cp scripts/tcl-tchord.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now tcl-tchord.service
```

服务运行后会监听在端口 `8998`，并自动连接 Home Assistant WebSocket 监听电视电源状态。

---

## 2. Home Assistant 配置 (`configuration.yaml`)

在 Home Assistant 的 `configuration.yaml` 中添加：

```yaml
# 1. 注册 REST 注入动作
rest_command:
  tcl_tchord_inject:
    url: "http://<SERVICE_HOST_IP>:8998/inject"
    method: POST

# 2. 注册实体按钮（用于 UI 触发）
template:
  - button:
      - name: "TCL T和弦声学重新校准"
        unique_id: tcl_tchord_recalibrate
        icon: mdi:tune-vertical
        press:
          - action: rest_command.tcl_tchord_inject
```

保存后在 **开发者工具 -> YAML** 中点击 **重载所有 YAML 配置**（或重启 HA）。

---

## 3. Lovelace 仪表盘卡片（Mushroom 赛博朋克风）

在仪表盘（如“客厅”或“影音”）中添加以下卡片配置：

```yaml
# 状态主卡片
- type: custom:mushroom-template-card
  primary: "TCL T和弦声学优化"
  secondary: "{{ states('sensor.tcl_tchord_status') }} · 点按重新校准"
  icon: mdi:speaker-multiple
  icon_color: "{% if '已优化' in states('sensor.tcl_tchord_status') %}teal{% elif '待机' in states('sensor.tcl_tchord_status') %}blue{% else %}grey{% endif %}"
  badge_icon: "{% if '已优化' in states('sensor.tcl_tchord_status') %}mdi:check-circle{% else %}mdi:clock-outline{% endif %}"
  badge_color: "{% if '已优化' in states('sensor.tcl_tchord_status') %}green{% else %}amber{% endif %}"
  tap_action:
    action: call-service
    service: button.press
    target:
      entity_id: button.tcl_the_xian_sheng_xue_zhong_xin_xiao_zhun
  hold_action:
    action: more-info
  entity: sensor.tcl_tchord_status
  card_mod:
    style: |
      ha-card {
        background: #101b1f;
        border: 1px solid rgba(83, 205, 181, 0.20);
        border-radius: 8px;
        box-shadow: none;
        --primary-text-color: #edf6f5;
        --secondary-text-color: #9bb2b0;
      }

# 声学校准指标标签卡片
- type: custom:mushroom-chips-card
  alignment: justify
  chips:
    - type: template
      icon: mdi:clock-fast
      content: "对齐: 85ms"
      tap_action:
        action: more-info
        entity: sensor.tcl_tchord_status
    - type: template
      icon: mdi:filter-variant
      content: "高通: 350Hz"
      tap_action:
        action: more-info
        entity: sensor.tcl_tchord_status
    - type: template
      icon: mdi:arrow-up-bold
      content: "人声: +3dB"
      tap_action:
        action: more-info
        entity: sensor.tcl_tchord_status
  card_mod:
    style: |
      ha-card {
        background: transparent;
        border: 0;
        border-radius: 0;
        box-shadow: none;
        --chip-background: #17292d;
        --chip-border-width: 1px;
        --chip-border-color: rgba(83, 205, 181, 0.18);
      }
```

---

## 4. 实体属性一览

点击卡片弹出 `more-info` 浮窗，可查看当前生效的所有声学校准属性：

| 属性 Key | 当前值 | 声学意义 |
| :--- | :--- | :--- |
| `state` | `已优化 (校准生效)` | 当前声学参数处于激活生效状态 |
| `tv_model` | `TCL 75Q9M Pro (MT9653)` | 电视硬件型号及芯片平台 |
| `soundbar_model` | `TCL Q95K 11.1.4 (Illusonic DSP)` | 回音壁声学架构及 DSP 类型 |
| `latency_pcm` | `48 ms` | PCM 双声道精准时延 |
| `latency_ddp_atmos` | `85 ms` | 杜比全景声 (E-AC-3 JOC) 补偿时延 |
| `latency_truehd_atmos` | `98 ms` | 杜比 TrueHD 无损全景声时延 |
| `latency_dts_x` | `88 ms` | DTS:X / DTS-HD MA 时延 |
| `crossover_frequency`| `350 Hz 高通分频` | 电视扬声器低频切除点，消除塑料共振 |
| `dialogue_elevation` | `+3 dB 屏幕中心抬升` | HRTF 纵向声场高度感强化 |
| `channel_mask` | `0xffffb (独立低音+环绕)` | 严格声道分离掩码 |
| `last_injected_time` | `2026-10-27 20:34:22` | 上次成功向 Audio HAL 注入的时间戳 |
| `disk_safety` | `100% 纯内存生效 (断电物理复原)` | 零刷机、零改写只读系统镜像 |
