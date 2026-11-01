# TCL MediaTek Pentonic 700 (MT9655 / MT9653) Audio HAL 逆向工程深度分析

## 1. 目标组件基本信息
* **芯片 SoC**：MediaTek MT9655 / MT9653 / Pentonic 700（平台代号：Merak）
* **系统环境**：Android 14 / Linux Kernel 5.15.167
* **目标驱动**：`/vendor/lib64/hw/audio.primary.merak.so`（AArch64 64位动态库，大小约 1.1MB）
* **系统保护机制**：`ro.boot.veritymode: enforcing`（dm-verity 强校验，禁止物理修改 `/vendor` 分区，一切调优需通过用户态/RAM 参数接口进行）

---

## 2. 关键导出符号与内部架构

在反汇编与符号表分析中，证实了 TCL 专属的 **TCSE (TCL Sound Enhancement) Tutti Choral** 核心函数与入口：

```
00000000000dcc30 T _Z42_utils_lapaf_get_tcse_tutti_choral_latencyP14mtk_stream_out
00000000000e4890 T _Z17cus_set_parameterP16mtk_audio_deviceP9str_parms
00000000000ef480 T _Z22cus_post_set_parameterP16mtk_audio_deviceP9str_parms
00000000000ec4b0 T _Z17cus_get_parameterP16mtk_audio_deviceP9str_parmsS2_
```

---

## 3. 核心逆向反汇编证据

### 3.1 时延参数切分逻辑 (`cus_set_parameter`)
在 `audio.primary.merak.so` 的 `0xe7818` - `0xe787c` 地址段，HAL 对传入的 `AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY` 字符串进行解析：

```arm
e780c: bl  str_parms_get_str   ; 从键值对中提取字符串
e7810: mov w21, w0             ; 保存返回值（字符串长度）
e7814: tbnz w0, #31, e788c     ; 检查是否有有效值
e7818: add x0, sp, #0x878      ; 参数缓冲区
e781c: bl  strdup              ; 复制参数字符串
e7828: add x1, x1, #0x608      ; 分隔符 "," (逗号)
e7834: bl  strtok_r            ; 使用逗号切分子串
e7840: add x25, x27, #0xda6    ; 结构体基地址偏移 0xda6 (十进制 3494)
e7850: bl  atoi                ; 将子串转换为整型毫秒值
e7858: strh w0, [x25, x24, lsl #1] ; 写入 16-bit 数组 (每个元素 2 字节)
e7868: bl  strtok_r            ; 获取下一个数字
e7874: cmp x24, #0xa           ; 最多允许 11 个槽位！(0 到 10)
e787c: b.cc e7850              ; 循环解析
e7884: bl  free                ; 释放临时缓冲区
```

### 3.2 11 个编解码器时延槽位映射 (`0xdcd20` - `0xdcf70`)
在 `_utils_lapaf_get_tcse_tutti_choral_latency` 中，系统根据当前播放流格式读取对应的时延值：

| 槽位 (Slot) | 结构体偏移 | 对应音频格式 | 日志调试格式串 |
| :--- | :--- | :--- | :--- |
| **Slot 0** | `adev + 3494` | **PCM / LPCM** | `%s: sbar pcm latency: %d` |
| **Slot 1** | `adev + 3496` | **Dolby Digital (AC3)** | `%s: sbar DD latency: %d` |
| **Slot 2** | `adev + 3498` | **Dolby Digital Plus (E-AC-3)** | `%s: sbar DDP latency: %d` |
| **Slot 3** | `adev + 3500` | **Dolby Atmos (E-AC-3 JOC)** | `%s: sbar DDP_ATMOS latency: %d` |
| **Slot 4** | `adev + 3502` | **Dolby TrueHD** | `%s: sbar TrueHD latency: %d` |
| **Slot 5** | `adev + 3504` | **TrueHD Dolby Atmos** | `%s: sbar TrueHD_ATMOS latency: %d` |
| **Slot 6** | `adev + 3506` | **Dolby MAT (PCM Atmos)** | `%s: PCM in, but sbar output mat, latency: %d` |
| **Slot 7** | `adev + 3508` | **DTS Core** | `%s: sbar dts(%d) latency: %d` |
| **Slot 8** | `adev + 3510` | **DTS-HD MA / DTS:X** | `%s: sbar dts(%d) latency: %d` |
| **Slot 9** | `adev + 3512` | 预留音频扩展位 1 | - |
| **Slot 10** | `adev + 3514` | 预留音频扩展位 2 | - |

---

### 3.3 原厂驱动中的返回值残留 Bug 分析 (Vendor Bug Report)

在对 `_Z17cus_set_parameter` 的逆向审计中，我们发现了一个典型的原厂编译器优化与代码编写缺陷：

1. **Bug 现场反汇编**：
   ```arm
   e780c: bl   10ae70 <str_parms_get_str@plt>
   e7810: mov  w21, w0         ; w21 保存了字符串长度（非负正整数，例如 32）
   ...
   e788c: adrp x1, 31000
   e7890: add  x1, x1, #0xa92  ; 查找下一个 key: AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL
   e7898: bl   10b2d0 <str_parms_has_key@plt>
   e789c: cbz  w0, e7e30       ; 如果没有传递 SBAR_CHANNEL，直接跳转到 e7e30！
   ...
   e7e2c: mov  w21, wzr        ; 重置 w21 = 0（这句代码竟然被放在了 SBAR_CHANNEL 处理块的末尾！）
   e7e30: adrp x1, 31000       ; 跳转目标直接跳过了 e7e2c！
   ...
   ; 在函数末尾：
   ; 返回寄存器 w0 被赋予了 w21 的值！
   ```

2. **后果与影响**：
   - 如果用户只单独设置 `AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY`，函数会成功解析并写入 11 个槽位，但由于跳过了 `w21 = 0` 的重置指令，函数向调用方返回了非零的字符串长度。
   - 上层 `adev_set_parameters` 检查 `if (ret != 0)`，误认为参数设置失败，从而在 logcat 中打印：
     `audio_hw_primary: adev_set_parameters: Set customer parameter fail. AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY=...`
   - **解决方案**：在注入参数时，应同时提交合法配对参数或通过原子参数批处理，确保状态机正确闭合。

---

### 3.4 电视内置扬声器 PEQ 参数控制协议 (`AQ_PEQ_PARAM`)

逆向证实，MediaTek HAL 支持通过标准键值对实时调整 `SpeakerOutput` 的参量均衡器（PEQ），这为在电视端注入 Linkwitz-Riley 高通滤波提供了完美的底层通道：

* **字符串格式**：
  ```text
  AQ_PEQ_PARAM=1;Fc=<截止频率>;Type=<滤波器类型>;AQ_DEVICE=SpeakerOutput;Q=<品质因数>;Band=<频段编号>;Gain=<增益dB>;Enable=1
  ```
* **参数字段定义**：
  * `AQ_DEVICE=SpeakerOutput`：目标设备为电视内置立体声扬声器；
  * `Type=0`：Peaking 峰值滤波；`Type=1`：Low-Pass 低通滤波；`Type=2`：High-Pass 高通滤波；
  * `Fc`：中心/截止频率（例如 `480` 代表 480Hz）；
  * `Q`：品质因数（以定点数放大 100 倍表示，如 `160` 代表 $Q = 1.6$；`71` 代表 $Q = 0.707$）；
  * `Band`：硬件双二阶滤波器段数（Band 1 到 Band 8）；
  * `Gain`：增益值（dB）。

---

### 3.5 完整的 TCSE 驱动参数全景表

```
┌──────────────────────────────────────┬─────────────┬────────────────────────────────────────────────────────┐
│ 参数名称                              │ 取值类型    │ 功能说明                                                │
├──────────────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ AQ_TCSE_ENABLE                       │ 0 / 1       │ TCL TCSE (TCL Sound Enhancement) 总引擎开关            │
│ AQ_TCSE_TUTTI_CHORAL_MODE            │ 0 / 1       │ T和弦协同发声模式总开关                                 │
│ AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY    │ 逗号分隔数组│ 回音壁各音频编码器 11 槽位时延微调表 (ms)               │
│ AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL    │ 整数掩码    │ 回音壁物理声道分工控制                                  │
│ AQ_TCSE_Speech_Clear                 │ 0 / 1 / 2   │ TCSE 人声对白清晰度硬件 DSP 增强 (直通对白提取算法)     │
│ AQ_TCSE_VERTICAL_SOUND_FIELD_MODE    │ 0 / 1       │ 垂直声场高度虚拟化模式                                  │
│ AQ_TCSE_VERTICAL_SOUND_FIELD_PARAMS  │ 格式串      │ 垂直声场提升增益与 HRTF 滤镜控制                        │
│ AQ_EARC_Delay                        │ 整数 (ms)   │ eARC 全局音频传输延迟补偿                               │
│ AQ_PEQ_PARAM                         │ 复合分号串  │ SpeakerOutput / Sbar PEQ 硬件双二阶滤波器参数           │
└──────────────────────────────────────┴─────────────┴────────────────────────────────────────────────────────┘
```
