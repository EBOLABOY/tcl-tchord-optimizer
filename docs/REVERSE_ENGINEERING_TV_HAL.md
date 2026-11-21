# TCL MediaTek Pentonic 700 (MT9655) Audio HAL 逆向工程深度分析 (v3.1 实证版)

## 1. 分析对象与证据链
* **目标设备**：TCL 75Q9M Pro（MediaTek MT9655 / 平台代号 `merak`，Android 14 `UTT2.250416.001`，`dm-verity: enforcing`）
* **完整反汇编二进制栈**：
  1. `/vendor/lib64/hw/audio.primary.merak.so`（主 Audio HAL，`cus_set_parameter`、TCSE 11 槽位时延）
  2. `/vendor/lib64/libaudiopipelinetopology.so`（APAF 管线路由，`setPeqParam`、`setVolOffset`、Dolby 参数解析）
  3. `/vendor/lib64/libCusAudioPipelineTopology_TITAN.so`（TCL 定制管线，`AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS`）
  4. `/vendor/lib64/libmi3_audio_hal.so`（含完整未剥离符号！`biquard_config`、`_MI_LAPAF_FILTER_MSE_PEQ_SetParameter`、`_MI_APAF_FILTER_VOLUME_SetVolumeOffset`）
  5. `/vendor/lib64/libthal_audio.so` & `/apex/com.tcl.tcore/lib64/hw/audio.tcl.default.so`（TCL 音频服务桥接，`thal_audio_set_peq`、`fpi_audio_set_sbar_latency`、AIAQ 线程）

---

## 2. 硬件 PEQ 引擎真相 (`AQ_PEQ_PARAM` — `libmi3_audio_hal.so`)

### 2.1 滤波器类型枚举（`biquard_config` @ `0x193050`）
反汇编证实 v2.x 文档中将 `Type=1` 和 `Type=2` 完全写反：

| `Type` 值 | 实际 DSP 滤波器类型 | `Q` 值内部缩放公式 | 允许 `Q` 整数范围 |
| :--- | :--- | :--- | :--- |
| **`0`** | **Peaking（峰值均衡）** | **`Q / 10.0`** | `5..160`（对应 `0.5..16.0`） |
| **`1`** | **HPF（高通滤波器）** | **`Q / 100.0`** | `50..90`（对应 `0.50..0.90`，Butterworth `0.707` = `71`） |
| **`2`** | **LPF（低通滤波器）** | **`Q / 100.0`** | `50..90`（对应 `0.50..0.90`） |
| **`3`** | **Low-Shelf（低频搁架）** | **`Q / 100.0`** | `50..90` |
| **`4`** | **High-Shelf（高频搁架）** | **`Q / 100.0`** | `50..90` |

* **`Gain` 单位**：`fixedpt_div(gain, 10.0)` —— **严格为 `0.1 dB`**（范围 `-180..+180`，即 `-18.0..+18.0 dB`；`+2.0 dB` 需传 `Gain=20`）。

### 2.2 13 个硬件频段与 AIAQ 免疫区发现（`Band 9..13`）
1. **`libmi3_audio_hal.so`** (`_MI_LAPAF_FILTER_MSE_PEQ_SetParameter` `0x18fcd4` & `_MI_LAPAF_FILTER_SetMsePeqBandParam` `0x191cd4`)：
   * 循环匹配 `Band01`..`Band13`（`cmn x25, #0xd`），校验 `cmp w19, #0xd`（0-based `band_id = 0..12`），**硬件实际支持 13 段双二阶滤波器**。
2. **`libthal_audio.so`** (`thal_audio_set_peq` `0x109b4`–`0x10a14`) 与 **`audio.tcl.default.so`** (`fpi_audio_set_peq` `0x3caf4`)：
   * `fpi_audio_set_peq` 上限写死为 **8 段**（`cmp w5, #0x8`），`thal_audio_set_peq` 循环 `x28 = -8..-1`、`w2 = w28 + 9`，**永远只覆写 `Band=1..8`**！
3. **结论**：将自定义 PBA 5 段滤波器（`Band 9..10` 300 Hz LR4 双阶高通 + `Band 11` 1 kHz 梳状抑止 + `Band 12..13` 4 kHz/8 kHz 人声与高空锚定）放置在 **`Band 9..13`**，可 **100% 免疫 TCL AIAQ 场景识别、音效模式切换与动态音量 PEQ 的后台覆盖**。

---

## 3. 硬件声级偏置真相 (`AQ_OUTPUT_VOL_OFFSET` + `OutputVolumeOffset`)
* **两级键名陷阱（重大发现）**：
  1. `audio.primary.merak.so` (`utils_set_output_volume` `0x94540`) 检查键 `AQ_OUTPUT_VOL_OFFSET` 与 `AQ_DEVICE=SpeakerOutput` 以进入路由分支；
  2. `libaudiopipelinetopology.so` (`setVolOffsetParam` `0x46064`, 字符串常量 `0x22acc`) 实际调用 `str_parms_get_int(parms, "OutputVolumeOffset", &offset)`！**若漏传 `OutputVolumeOffset`，`offset` 永远为 `0`，完全不生效！**
* **0.1 dB 硬件单位**（`libmi3_audio_hal.so` `_MI_APAF_FILTER_VOLUME_SetVolumeOffset` `0x14aba0` + `_MI_APAF_FILTER_CalcFinalGainDb` `0x146af0`）：
  * 公式：`final_gain = volume_curve[idx] + offset + extra`，范围 `-1200..+120`（`-120.0..+12.0 dB`）。
  * 正确指令：**`AQ_OUTPUT_VOL_OFFSET=1;OutputVolumeOffset=-80;AQ_DEVICE=SpeakerOutput`**。
  * **实机 `logcat` 验证**（音量 8 基准）：下发 `OutputVolumeOffset=0` 时 `<APAF> Set VolGain(step):-370`（`-37.0 dB`）；下发 `OutputVolumeOffset=-70` 为 `-440`（`-44.0 dB`）；v3.1 下发 `OutputVolumeOffset=-80` 后瞬时变为 **`Set VolGain(step):-450`（`-45.0 dB`，精确衰减 `-8.0 dB`）**。
* 因为 `offset` 独立存储并与音量曲线相加，用户使用遥控器调节音量时该 `-8.0 dB` 相对衰减会自动保持。

---

## 4. 字符串开关与无效参数纠正
1. **必须传 `"On"` / `"Off"` 的参数**：
   * `AQ_TCSE_ENABLE`（`audio.primary.merak.so` `0xe4b94`）
   * `AQ_DolbyDialogEnhancerEnable`（`libaudiopipelinetopology.so` `0x4d320`）
   * `AQ_DolbyVolumeLevler`（`libaudiopipelinetopology.so` `0x4df00`）
   * 传 `"1"` 会被判为不等于 `"On"`，从而直接被**关闭（置 0）**！
2. **`AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL`**：
   * 按 3 字节声道结构 `(b2<<16)|(b1<<8)|b0` 拼接加载 `dolby_dap_tuning_config_T_<b2><b1><b0>.dat`。传入 `16777215` (`0xFFFFFF`) 会尝试加载不存在的 `T_255255255.dat` 导致报错。**严禁覆盖**。
3. **`AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS`**：
   * `libCusAudioPipelineTopology_TITAN.so` (`0xf9e0`–`0xfacc`) 使用逗号分隔 + `atoi()` 解析进 `uint8_t[64]`。传 `"elevation_gain=3dB,..."` 全被解析为 `[0, 0, 0]`。**v3.0 已移除**。
4. **`adev_set_parameters` 恒返回 `0`**：
   * `audio.primary.merak.so` (`0x65980`–`0x66f10`) 无论内部解析是否成功均向上层返回 `0`。因此必须通过 `logcat` 捕获 `<APAF> ... Set VolGain(step):<N> ... SPEAKER` 与 `audio_hw_primary: setPeqParam: Speaker_MsePeq set peqparam).` 以及零错误码作为生效判据。

---

## 5. 真实的 11 槽位编码器时延映射 (`0xdcc30`–`0xdd1ec`)

在 `_utils_lapaf_get_tcse_tutti_choral_latency` 中，11 个 `uint16_t` 槽位（`adev + 0xda6`）的真实对应关系如下（同时支持 `vendor.hal.audio.tchor.offset` 全局微调属性）：

| 槽位 | 偏移 | 真实音频格式 | 说明 |
| :--- | :--- | :--- | :--- |
| **Slot 0** | `+3494` | **PCM / LPCM** | 普通 PCM |
| **Slot 1** | `+3496` | **Dolby Digital (AC-3)** | 杜比数字 |
| **Slot 2** | `+3498` | **Dolby Digital Plus (E-AC-3)** | 杜比数字+ |
| **Slot 3** | `+3500` | **Dolby Digital Plus + Atmos (E-AC-3 JOC)** | 流媒体全景声 |
| **Slot 4** | `+3502` | **Dolby TrueHD** | 蓝光无损 |
| **Slot 5** | `+3504` | **Dolby TrueHD + Atmos** | 蓝光无损全景声 |
| **Slot 6** | `+3506` | **Dolby MAT (PCM)** | Xbox / Apple TV MAT |
| **Slot 7** | `+3508` | **Dolby MAT + Atmos** | Xbox / Apple TV MAT 全景声（v2.x 误标为 DTS Core！） |
| **Slot 8** | `+3510` | **DTS Core** | DTS 5.1 |
| **Slot 9** | `+3512` | **DTS-HD** | DTS-HD HRA（v2.x 误标为 Reserved！） |
| **Slot 10** | `+3514` | **DTS:X / DTS-HD MA** | DTS:X（v2.x 误标为 Reserved！） |
