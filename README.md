# TCL T-Chord Joint Optimizer (TCL T和弦声学协同优化中枢 v3.1)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![TV](https://img.shields.io/badge/TV-TCL%2075Q9M%20Pro%20(MT9655%20%2F%20Onkyo%202.1.2)-orange.svg)](docs/REVERSE_ENGINEERING_TV_HAL.md)
[![Soundbar](https://img.shields.io/badge/Soundbar-TCL%20Q95K%2011.1.4%20(MT8532%20%2B%20Illusonic)-blueviolet.svg)](docs/REVERSE_ENGINEERING_SOUNDBAR.md)
[![Acoustics](https://img.shields.io/badge/Acoustics-JAES%20PBA%20%7C%20300Hz%20LR4%20%7C%20--8dB%20ICLD-brightgreen.svg)](docs/ACOUSTIC_THEORY_AND_TUNING.md)
[![Safety](https://img.shields.io/badge/Safety-100%25%20In--RAM%20(Zero%20Flash%20Write)-success.svg)](#4-安全保障与-100-物理回退)

**TCL T-Chord Joint Optimizer v3.1** 是专为 **TCL 75Q9M Pro 电视（Pentonic 700 / MT9655 / Android 14 / 安桥 2.1.2 5单元 80W）** 与 **TCL Q95K 11.1.4 回音壁（MT8532 / StreamSDK 26.02-Gallium / Illusonic DSP Type 13 / 22单元 + 双7吋推挽独立低音炮）** 打造的**全链路二进制实证 + 感知频段分配（PBA）内存级声学校准中枢**。

---

## 1. 相比原厂 T和弦（原生使用）的核心差异

| 对比维度 | 原生 T和弦（默认出厂） | 本项目 v3.1（PBA 校准生效） |
| :--- | :--- | :--- |
| **Q95K 编解码时延对齐** | 由 Q95K 通过 HDMI-CEC `0xA0/0x1B` 上报出厂实测延迟表 | **100% 保留原生 CEC 协商时延与声道配置**（不覆写、不破坏唇音同步） |
| **电视端低频处理 (`<300 Hz`)** | 电视 20W 背部小低音与 Q95K 低音炮重叠发声，易引起箱体共振与低频相位抵消 | **Band 9 & 10 级联 300 Hz LR4 真高通（24 dB/oct，`Type=1`）**：150 Hz 衰减 -24 dB、100 Hz 以下综合衰减超 **-46 dB**，彻底卸载机身共振，低频 100% 交由 Q95K 双 7 吋推挽低音炮 |
| **电视/回音壁声级平衡 (ICLD)** | 电视与回音壁同级混响（`0 dB` 偏移），易产生垂直梳状滤波发空与双声源分裂 | **真实 `-8.0 dB` 硬件衰减**（`OutputVolumeOffset=-80`，实机 `<APAF>` 增益验证精确降 7–8 dB），Q95K 保留 86% 声功率主权，梳状波谷大幅收敛 |
| **垂直声像与对白抬升（PBA）** | 宽带粗放混合，无频段针对性塑形；后台 AIAQ 每 5–30 秒还会往 `Band 1..8` 注入 +9 dB 低音提升 | 依据 **Wallis & Lee (JAES 2016 / Appl. Sci. 2020)** 与 **Lee PBA (JAES 2016)**，在 **AIAQ 免疫区 `Band 11..13`** 实施 3 段精准塑形：<br>• `1 kHz` `-2.0 dB`（净 `-10.0 dB`，抑制梳状桶音与 Blauert 后向带）<br>• `4 kHz` `+2.0 dB`（净 `-6.0 dB`，越过 `-7 dB` 阈值，借腹语效应锚定唇音到屏幕正中）<br>• `8 kHz` `+1.5 dB`（净 `-6.5 dB`，Blauert 真实 `Oben` 上方空气线索） |
| **后台 AIAQ 抗覆盖能力** | 电视 AIAQ 与音效切换频繁覆写 `Band 1..8` | 全部 5 组滤波器运行于硬件 **`Band 9..13`**（`libmi3_audio_hal.so` 共 13 段，TCL 仅写 `Band 1..8`），**100% 免疫覆盖** |
| **生效验证与诊断** | 无可见状态 | 每次注入自动核验电视 `logcat` 中 `<APAF>` `VolGain(step)` 与 `Speaker_MsePeq` 回执；`--diagnose` 同时读取 Q95K StreamSDK（只读）与 HDMI-CEC `TclHdmiTvClient` TRD 实时状态 |

---

## 2. 二进制逆向与学术文档索引

* 📄 [心理声学理论与 PBA 调校规范](docs/ACOUSTIC_THEORY_AND_TUNING.md) — JAES 2015–2021 / Applied Sciences 2017 & 2020 / Blauert 1997 完整推导与微调指南
* 📄 [电视 MediaTek Audio HAL 逆向工程](docs/REVERSE_ENGINEERING_TV_HAL.md) — `Type=1` 真高通、`OutputVolumeOffset` 两级键名、0.1 dB 单位、`Band 9..13` 免疫区、真实 11 槽位映射
* 📄 [TCL Q95K 回音壁逆向与 HDMI-CEC 协议](docs/REVERSE_ENGINEERING_SOUNDBAR.md) — StreamSDK 26.02 只读节点与完整 `0xA0` TRD/T-Symphony 协议表
* 📄 [Home Assistant 自动化集成指南](docs/HOME_ASSISTANT_INTEGRATION.md) — Systemd 守护服务、开机自愈与动态 Mushroom 卡片

---

## 3. 快速上手

```bash
# 1. 全链路诊断（电视 HAL + HDMI-CEC Q95K TRD 状态 + StreamSDK 只读遥测）
python3 t_chord_joint_orchestrator.py --diagnose

# 2. 一键应用 v3.1 PBA 声学校准并自动通过电视 logcat 核验 DSP 生效
python3 t_chord_joint_orchestrator.py --apply

# 3. 完整恢复出厂默认（清零 Band 9..13 及遗留 Band 1..4、复位 OutputVolumeOffset 与旧持久化设置）
python3 t_chord_joint_orchestrator.py --restore

# 4. 查看当前 JSON 解析出的底层 HAL 指令
python3 t_chord_joint_orchestrator.py --show-params
```

---

## 4. 安全保障与 100% 物理回退

1. **零磁盘修改**：不触碰 `/system`、`/vendor`、`/boot`，不影响 dm-verity/AVB。
2. **严格遵守设备认证边界**：Q95K `:8043` 仅执行只读 `getData`/`getRows` 遥测，不尝试绕过 `authMode=setData`。
3. **纯内存完全可逆**：执行 `--restore` 或电视重启即 100% 恢复原生出厂状态。

---

## 5. 项目结构

```text
├── configs/
│   └── default_codec_latency.json      # v3.1 PBA 声学校准配置（修改即热生效）
├── docs/
│   ├── ACOUSTIC_THEORY_AND_TUNING.md   # JAES/AES 心理声学理论与 PBA 微调指南
│   ├── HOME_ASSISTANT_INTEGRATION.md   # Home Assistant 开机自愈与动态仪表盘
│   ├── REVERSE_ENGINEERING_SOUNDBAR.md # Q95K StreamSDK 与 HDMI-CEC TRD 协议分析
│   └── REVERSE_ENGINEERING_TV_HAL.md   # 电视 MediaTek Audio HAL 反汇编实证
├── injector/
│   ├── bin/audiotool.jar               # 已编译 DEX 工具包（app_process 反射调用）
│   └── src/AudioTool.java              # AudioSystem + TclHdmiTvClient 注入/查询源码
├── scripts/
│   ├── live_dolby_monitor.py           # 实时音频管线与 HAL 监听诊断工具
│   ├── t_chord_service.py              # Home Assistant WebSocket 桥接与 HTTP 服务 (:8998)
│   └── tcl-tchord.service              # Systemd 服务单元模板
├── t_chord_joint_orchestrator.py       # 主命令行编排器（--apply/--restore/--diagnose）
├── LICENSE
└── README.md
```

---

## 6. 开源协议

基于 [MIT 协议](LICENSE) 开源。
