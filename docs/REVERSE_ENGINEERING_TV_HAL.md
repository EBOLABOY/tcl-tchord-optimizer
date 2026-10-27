# TCL MediaTek Pentonic 700 (MT9653) Audio HAL 逆向工程分析

## 1. 目标组件基本信息
* **芯片 SoC**：MediaTek MT9653 / Pentonic 700（代号 Merak）
* **系统环境**：Android 14 / Linux Kernel 5.15.167
* **目标驱动**：`/vendor/lib64/hw/audio.primary.merak.so`（AArch64 64位动态库，大小约 1.1MB）
* **AVB 机制**：`ro.boot.veritymode: enforcing`（dm-verity 强校验，禁止物理修改 `/vendor` 分区）

---

## 2. 关键导出符号与内部架构

在反汇编与符号表分析中，发现了 TCL 专属的 **TCSE (TCL Sound Enhancement) Tutti Choral** 核心函数：

```
00000000000dcc30 T _Z42_utils_lapaf_get_tcse_tutti_choral_latencyP14mtk_stream_out
00000000000e780c T _Z17cus_set_parameterP16mtk_audio_deviceP9str_parms
```

---

## 3. 核心逆向反汇编证据

### 3.1 时延参数切分逻辑 (`cus_set_parameter`)
在 `audio.primary.merak.so` 的 `0xe7818` - `0xe787c` 地址段，HAL 对传入的参数字符串进行解析：

```arm
e7818: add x0, sp, #0x878      ; 参数缓冲区
e781c: bl  strdup              ; 复制参数字符串
e7834: bl  strtok_r            ; 使用分隔符逗号 "," 进行切分
e7840: add x25, x27, #0xda6    ; 结构体基地址偏移 0xda6 (十进制 3494)
e7850: bl  atoi                ; 将子串转换为整型毫秒值
e7858: strh w0, [x25, x24, lsl #1] ; 写入 16-bit 数组 (每个元素 2 字节)
e7874: cmp x24, #0xa           ; 最多允许 11 个槽位！
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

### 3.3 回音壁物理声道分配 (`AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL`)
在 `0xe792c` 处：
```arm
e792c: and w9, w22, #0xffffff
e7930: str w9, [x27, #3488]    ; 写入 adev + 3488 声道掩码寄存器
```
* 当掩码传入 `0xffffb`（十进制 `1048571`）时，系统指示回音壁将声学重心聚焦于环绕、顶置天花和超低音频段，而中置对白频段交由电视屏幕扬声器负责。
