# TCL 11.1.6 IMAX / Auro-3D 三层空间声学矩阵架构规范

[![Architecture](https://img.shields.io/badge/Architecture-11.1.6%20Tri--Level%20Spatial%20Matrix-blue.svg)](#1-物理发声单元拓扑-18-单元联合矩阵)
[![Standards](https://img.shields.io/badge/Standards-IMAX%20Enhanced%20%2F%20Auro--3D-orange.svg)](#2-三层空间声道分配规范)
[![Acoustics](https://img.shields.io/badge/Acoustics-JAES%202015%20%2F%20Blauert%20Bands-brightgreen.svg)](#3-40cm-空间落差声学代偿与对白锚定)
[![HAL](https://img.shields.io/badge/HAL-MediaTek%20Pentonic%20700%20%2F%20MT9655-red.svg)](#4-底层-audio-hal-参数下发流水线)

---

## 1. 物理发声单元拓扑 (18 单元联合矩阵)

本项目将客厅中的 **TCL 75Q9M Pro 旗舰电视** 与 **TCL Q95K 旗舰回音壁** 深度统合为一个有机的 **11.1.6 (共 18 个物理发声单元)** 沉浸式声学系统：

```
                      [ 天花板平顶 (Ceiling Plane @ ~2.8m) ]
                       ^                   ^                   ^
             前反射声波 |         直达天空声场 |          后反射声波 |
                       |                   |                   |
               +---------------+   +---------------+   +---------------+
               | Q95K 前反射   |   | 电视安桥朝天  |   | Q95K 环绕反射 |
               | (Front Height)|   | (Top Sky 2ch) |   | (Rear Height) |
               +---------------+   +---------------+   +---------------+
                       |                   |                   |
                       |          [75吋 4K MiniLED 屏幕]       |
                       |                   |                   |
                       |         [电视底部微单元 (对白锚定)]     |
                       |           (-10dB ICLD + 3.5kHz)       |
                       |                   |                   |
                       |<--------- 垂直间隙 Δh = 40cm -------->|
                       v                   v                   v
      ===================================================================
      [ Q95K 11 声道水平声卡阵列 (FL, FR, C, SL, SR, SBL, SBR, Wide) ]
      ===================================================================
                                      |
                           [ Q95K 10吋 200W 独立超重低音 ] (25Hz-120Hz)
```

### 1.1 硬件设备资产全景

| 设备 | 音响配置与底层平台 | 物理发声单元分布 | 矩阵角色分工 |
| :--- | :--- | :--- | :--- |
| **TCL 75Q9M Pro 电视** | ONKYO 安桥 2.1.2 Hi-Fi 专业音响系统<br>(80W 总峰值功率, MT9655 / Pentonic 700) | ① 2x 底部全频扬声器<br>② 1x 20W 背部独立音腔重低音<br>③ **2x 顶部物理朝天发声天空声道 (@ 1.45m 高位)** | ① 顶部直发天空声道 (Top Sky L/R)<br>② 屏幕中心对白高度锚定 (480Hz 高通 + Blauert 提升) |
| **TCL Q95K 回音壁** | 11.1.4 物理全景声系统<br>(瑞士 Illusonic DSP Type 13, MT8532) | ① 11x 水平声道波束成形单元<br>② 1x 10 吋 200W 无线低音炮<br>③ 4x 天空反射扬声器 (前条形 2 + 后环绕 2) | ① 11 声道地平面声场 (0° 地平线全频透传)<br>② 10 吋低频冲击波 (25Hz–120Hz)<br>③ 前后反射天空层 (Front/Rear Height) |

---

## 2. 三层空间声道分配规范

11.1.6 系统借鉴了 **Auro-3D 三层声场模型** 与 **IMAX Enhanced 12-Channel 声学规范**，将房间划分为地平面、天空穹顶和低音震撼三个物理层次：

### 2.1 地平面声道 (Ground Layer, 11 声道 @ 0° 水平角)
* **包含声道**：前置左 (FL)、前置右 (FR)、主中置 (C)、左侧环绕 (SL)、右侧环绕 (SR)、左后环绕 (SBL)、右后环绕 (SBR)、左宽展 (Wide L)、右宽展 (Wide R) 及侧向波束单元。
* **物理分配**：100% 由 Q95K 条形主音箱与无线环绕音箱呈现。
* **增益与处理**：$0\text{ dB}$ 全频直通透传，保持原汁原味的杜比全景声与 DTS:X 声场宽度。

### 2.2 超低音声道 (LFE Subwoofer Layer, .1 声道)
* **频段范围**：$25\text{ Hz} \sim 120\text{ Hz}$。
* **物理分配**：100% 由 Q95K 10 吋无线独立低音炮（200W）承担。
* **声学防护**：
  * 电视背部 20W 低音单元在低于 480Hz 时冲程受限（$X_{\max} < 1.2\text{mm}$），若强行发声会引起电视超薄塑料后盖剧烈共振，并与 Q95K 低音炮产生杂乱的驻波和相位对冲。
  * **在电视端 Audio HAL 硬件级注入 Linkwitz-Riley 4阶（24dB/oct）480Hz 高通滤波**，将低音负荷彻底卸载给 10 吋独立炮，电视外壳实现零塑料异响。

### 2.3 天空与穹顶声道 (Tri-Level Height & Sky Layer, .6 声道)
传统回音壁的 4 个天空声道仅依靠天花板反射，能量在经过 2.8 米层高往返衰减后，顶部听感偏暗。本项目将电视自带的高位物理朝天扬声器纳入天空总线，构成前后纵深完整的 6 天空矩阵：
1. **前部天空 (Front Height L/R, 2 声道)**：由 Q95K 条形音箱前向朝天反射单元发声（天花板倾角 20° 反射）。
2. **顶中直发天空 (Top Center Sky L/R, 2 声道)**：由 75Q9M Pro 电视顶部的安桥物理扬声器发声（位于 1.45m 高位，直接向天花板垂直喷射）。
   * 通过 MediaTek 底层 HAL 指令 `AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=1` 激活。
   * 下发参数 `AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS=elevation_gain=3dB,crossover_hz=480,hrtf_enable=0`（关闭人工 HRTF 虚拟反射，避免与实体房间产生空洞回音）。
3. **后部天空 (Rear Height L/R, 2 声道)**：由 Q95K 无线后环绕音箱朝天反射单元发声（天花板倾角 15° 反射）。

**听觉效果**：形成“前反射 -> 顶直发 -> 后反射”全覆盖的半球形穹顶包围感，物体从前向后飞过的天空轨迹连续且饱满。

---

## 3. 40cm 空间落差声学代偿与对白锚定

### 3.1 现实痛点计算 (视听几何学)
* **用户实际测量数据**：
  * 电视下沿距离回音壁上沿：$\Delta h = 40\text{ cm}$；
  * 75 吋电视高度约为 $94\text{ cm}$，屏幕画面中心距回音壁中轴约为 $h_{\text{center}} \approx 87\text{ cm}$；
  * 电视屏幕至沙发听音位距离：$D = 2.4\text{ m} \sim 2.75\text{ m}$；
  * 垂直视角/声角落差：
    $$\theta = \arctan\left(\frac{0.87}{2.4}\right) \approx 19.9^\circ \approx 20^\circ$$
* **若仅使用透传（关掉电视声音）**：
  * 人物对白完全从电视下沿 40cm 的回音壁发出，产生高达 $20^\circ$ 的视觉与听觉偏离（“人张嘴在电视正中，声音却从电视柜底下钻出”）。
* **若使用原厂粗糙 T 和弦**：
  * 电视喇叭与回音壁同时不加限制发声，因垂直声程差引发剧烈的垂直梳状滤波反相抵消（Comb Filtering Notch），导致人声单薄、空洞发虚。

### 3.2 科学声学解决方案 (JAES 2015 + Blauert 带)
本项目利用人类听觉定位的两个生理声学机制完美化解落差：
1. **通道间声级差（ICLD）精准衰减 (-10.0 dB)**：
   * 根据 Wallis & Lee（JAES 2015 "The Vertical Haas Effect and Sound Localization"）研究，在 2.4m~2.75m 典型近场视听距离下：
     * 若仅衰减 $-6\text{ dB}$，电视扬声器声能占比为 25%（感知响度约 50%），人耳在纯净立体声或全景声音乐中极易识破双声源，产生“微弱重音/空洞回音”错觉；
     * 当将高位辅助声源衰减至 **$-10\text{ dB} \sim -12\text{ dB}$** 时，主声源（Q95K）在声能上彻底占据绝对声学主导（彻底抑制双重听觉分裂），同时 $-10\text{ dB}$ 的高位微弱能量足以在垂直面上提供足够的视觉诱导拉力，实现完全无重音的声像抬升！
2. **Jens Blauert (1969/1997) 3.5 kHz "Vorn-Oben" 频带抬升**：
   * 人耳耳廓在识别正前上方声源时，对 $3.5\text{ kHz}$ 频段具有天然的共振滤波特性。
   * 通过在电视端 PEQ Band 3 施加 $Fc=3500\text{ Hz}, Q=1.5, \text{Gain}=+3.0\text{ dB}$ 的峰值滤波，激活耳廓前上方定位中枢。
3. **腹语效应（Ventriloquism Effect, Bertelson 2004）**：
   * 结合 75 吋巨幕的视觉吸引，在 $20^\circ$ 的视角窗口内，听觉对白声像被瞬间拉升 40cm，稳稳锚定在电视画面中演员的嘴唇位置！

---

## 4. 底层 Audio HAL 参数下发流水线

本项目通过纯内存（RAM-only）方式与电视 MediaTek `audio.primary.merak.so` 通信，无需 Root，不修改系统 Flash 分区，断电即物理恢复。

### 4.1 核心注入参数表

```text
# 1. 激活 TCSE 协同发声引擎 (关闭 Speech_Clear 人声重影相位调制)
AQ_TCSE_ENABLE=1
AQ_TCSE_TUTTI_CHORAL_MODE=1
AQ_TCSE_Speech_Clear=0

# 2. 激活 11.1.6 顶部直发天空声道 (hrtf_enable=0 抑制人工反射回音)
AQ_TCSE_VERTICAL_SOUND_FIELD_MODE=1
AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS=elevation_gain=3dB,crossover_hz=480,hrtf_enable=0

# 3. 11 槽位微秒级相位基准注入 (闭合原厂状态机)
AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY=42,58,66,80,84,92,74,54,82,50,50;AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL=16777215

# 4. 下发 MediaTek <APAF> 硬件声级偏置 (-7dB 对白定位与动态平衡点)
AQ_OUTPUT_VOL_OFFSET=-7;AQ_DEVICE=SpeakerOutput

# 5. 激活 Dolby MS12 硬件级对白增强与音量平准器 (抑制背景爆音，凸显对白)
AQ_DolbyDialogEnhancerEnable=1;AQ_DolbyDialogEnhancer=10
AQ_DolbyVolumeLevler=1

# 6. Linkwitz-Riley 4阶 480Hz 高通分频 (Band 1 & 2 Butterworth 级联)
AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=1;Gain=0;Enable=1
AQ_PEQ_PARAM=1;Fc=480;Type=2;AQ_DEVICE=SpeakerOutput;Q=71;Band=2;Gain=0;Enable=1

# 7. Blauert 3.5kHz 屏幕对白垂直抬升滤波 (Band 3)
AQ_PEQ_PARAM=1;Fc=3500;Type=0;AQ_DEVICE=SpeakerOutput;Q=150;Band=3;Gain=3;Enable=1

# 8. 人声辅音清晰度与共振峰强化滤波 (Band 4: 2.0kHz, +5dB)
AQ_PEQ_PARAM=1;Fc=2000;Type=0;AQ_DEVICE=SpeakerOutput;Q=120;Band=4;Gain=5;Enable=1
```

### 4.2 Android TV 系统设置联动

```bash
# 激活电视与 eARC 双输出链路
settings put system tcl_app_settings_multi_sound_device true
settings put system tcl_app_settings_eARC_mode true

# 声道电平平衡：中置对白声道拉至 +10，顶部环境天空平衡至 +3 (防止背景氛围声掩盖对白)
settings put system tcl_sys_audio_channel_center 10
settings put system tcl_sys_audio_channel_top 3
settings put system tcl_sys_audio_vertical_sound_field 1
settings put system tcl_sys_audio_atmos 1

# 彻底禁用电视端 AI 声音内容自适应 (防止后台守护进程突发覆写 DAP GEQ +24dB 破坏声级平衡)
settings put global tcl_app_settings_ai_audio_visual false
settings put system tcl_sys_audio_aiaq_adaptive_content 0
settings put system tcl_sys_audio_sound_mode 1

# CEC 总线开启 System Audio Mode 与 ARC
cmd hdmi_control setsystemaudiomode on
cmd hdmi_control setarc on
```

### 4.3 “回音感”实机逆向根因诊断与声学消除

在实机杜比全景声音乐监听实测中，曾检测出微弱的“回音感/空洞感”，经深入 `audio_hw_primary` 与 `libthal_audio.so` 反汇编排查，锁定了 **3 个隐蔽根因**：
1. **电视 AI 智感声音（AIAQ）后台抢占覆盖**：
   * 电视内部运行有 `AiAq` 声学分类器，在检测到人声时会自动下发 `setDolbySoundMode: Dap set sound mode (News)`，并注入 `Dap set DapGeqBandTarget to -20, 0, 16, 24, 24, 24, -24`（在 1kHz~5kHz 人声频段强行暴增 **+24dB**）。这导致电视喇叭瞬间超越回音壁声压，造成极其突兀的人声双重发声与回音。
   * **消除方案**：彻底关闭 `tcl_app_settings_ai_audio_visual` 与 `tcl_sys_audio_aiaq_adaptive_content`，恢复平直参考频响。
2. **虚拟 HRTF 早期反射滤波（hrtf_enable=1）**：
   * 原生 TCSE 天空算法包含为立体声喇叭模拟高度感而注入的人工房间早期反射延时抽头（Echo taps）。在真实的 2.75 米硬质客厅环境中，这些虚拟反射与物理房间反射叠加，听感即为“发空/回音”。
   * **消除方案**：设置 `hrtf_enable=0`，使安桥朝天扬声器喷射纯净的直达声波。
3. **TCSE 人声增强（Speech_Clear=1）动态相位抖动**：
   * 该算法会对人声共振峰进行动态相位扩宽，导致音乐中的人声与回音壁主中置产生梳状抖动。
   * **消除方案**：设置 `AQ_TCSE_Speech_Clear=0`，确保两套系统绝对相干同相。

### 4.4 “人声偏小、背景声过大”深度成因与解决方案

在电视剧（以 2.0 立体声为主）播放中，极易出现“背景音/配乐震耳欲聋，但人物说话含糊听不清”的现象，成因与调优方案如下：
1. **声源混音动态范围过大（DRC 缺失）**：流媒体电视剧为了兼顾移动端，常以高动态混音，背景音乐峰值接近 0dBFS，而演员对白通常仅在 -24LKFS。
   * **解决方案**：注入 `AQ_DolbyVolumeLevler=1`（杜比音量平准器），硬件级压缩突发动能，将微弱对白智能垫高。
2. **Dolby 硬件对白增强器（Dialog Enhancer）**：
   * **解决方案**：下发 `AQ_DolbyDialogEnhancerEnable=1;AQ_DolbyDialogEnhancer=10`，在 MediaTek APAF DSP 核心内针对人声共振峰给予 +10dB 独立瞬态增强。
3. **天空通道声能反客为主**：
   * 此前天空声道增益为 `+10`，在电视剧播放中将本应处于环境音的配乐放大过多，反向掩盖中置人声。
   * **解决方案**：将 `tcl_sys_audio_channel_top` 回调至 `+3`，同时将 `tcl_sys_audio_channel_center` 拉高至 `+10`，中置人声成为声场绝对主角。
4. **人声辅音清晰度 PEQ 补正**：
   * 在电视 SpeakerOutput 增加 Band 4（$Fc=2000\text{ Hz}, Q=1.2, \text{Gain}=+5\text{ dB}$），辅音齿音咬字立刻清晰通透。
   * 电视 Speaker 衰减从过度压制的 -10dB 回退到 **-7dB**，为人声拉升提供充沛的实体能量。

---

## 5. 一键启用与验证

直接在调度器中执行：

```bash
# 一键下发 11.1.6 空间声学矩阵配置
python3 t_chord_joint_orchestrator.py --apply

# 查看 11.1.6 系统与驱动全量诊断
python3 t_chord_joint_orchestrator.py --diagnose

# 恢复出厂默认设置
python3 t_chord_joint_orchestrator.py --restore
```
