# Home Assistant 自动化与状态监控集成指南 (v3.1)

后台守护服务 [`scripts/t_chord_service.py`](../scripts/t_chord_service.py) 通过带心跳保活（`heartbeat=30s`）的 Home Assistant WebSocket 实时监听电视开机状态：
1. **开机自愈**：电视由 `off/standby/unavailable` 切入开机态 4 秒后，自动下发 v3.1 PBA 校准并在电视 `logcat` 中核验生效。
2. **动态状态上报**：自动从 `configs/default_codec_latency.json` 读取当前分频点、ICLD 衰减与 5 段 PBA 曲线，写入 `sensor.tcl_tchord_status`。
3. **一键校准与还原**：提供 `POST :8998/inject`、`POST :8998/restore`、`GET :8998/status`、`GET :8998/diagnose`。

---

## 1. 部署 Systemd 服务

参考模板 [`scripts/tcl-tchord.service`](../scripts/tcl-tchord.service)，安装至 `/etc/systemd/system/tcl-tchord.service` 并填入你的 HA Long-Lived Access Token：

```ini
[Unit]
Description=TCL T-Chord Joint Optimizer Service & Home Assistant Bridge
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/tcl-tchord-optimizer
Environment=HA_HOST=192.168.100.4
Environment=HA_PORT=8123
Environment=HA_TOKEN=YOUR_HA_LONG_LIVED_ACCESS_TOKEN
Environment=TV_IP=192.168.100.101
Environment=HA_ENTITY_ID=media_player.ke_ting_dian_shi
ExecStart=/usr/bin/python3 /root/tcl-tchord-optimizer/scripts/t_chord_service.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now tcl-tchord.service
```

---

## 2. Home Assistant 配置 (`configuration.yaml`)

```yaml
rest_command:
  tcl_tchord_inject:
    url: "http://<SERVICE_HOST_IP>:8998/inject"
    method: POST
  tcl_tchord_restore:
    url: "http://<SERVICE_HOST_IP>:8998/restore"
    method: POST

template:
  - button:
      - name: "TCL T和弦声学重新校准"
        unique_id: tcl_tchord_recalibrate
        icon: mdi:tune-vertical
        press:
          - action: rest_command.tcl_tchord_inject
      - name: "TCL T和弦恢复出厂默认"
        unique_id: tcl_tchord_restore
        icon: mdi:restore
        press:
          - action: rest_command.tcl_tchord_restore
```

---

## 3. Lovelace 动态仪表盘卡片（Mushroom 风格）

标签内容直接读取 `sensor.tcl_tchord_status` 实时属性，修改 JSON 后自动同步：

```yaml
- type: custom:mushroom-template-card
  primary: "TCL T和弦声学优化 (v3.1 PBA)"
  secondary: "{{ states('sensor.tcl_tchord_status') }} · 点按重新校准"
  icon: mdi:speaker-multiple
  icon_color: "{% if '已优化' in states('sensor.tcl_tchord_status') %}teal{% elif '待机' in states('sensor.tcl_tchord_status') %}blue{% else %}grey{% endif %}"
  tap_action:
    action: call-service
    service: button.press
    target:
      entity_id: button.tcl_the_xian_sheng_xue_zhong_xin_xiao_zhun
  hold_action:
    action: more-info
  entity: sensor.tcl_tchord_status

- type: custom:mushroom-chips-card
  alignment: justify
  chips:
    - type: template
      icon: mdi:filter-variant
      content: "{{ state_attr('sensor.tcl_tchord_status', 'crossover_frequency') or '300Hz LR4' }}"
    - type: template
      icon: mdi:volume-minus
      content: "ICLD: {{ state_attr('sensor.tcl_tchord_status', 'icld_level_balance') or '-8.0 dB' }}"
    - type: template
      icon: mdi:clock-check-outline
      content: "原生 CEC 时延"
```
