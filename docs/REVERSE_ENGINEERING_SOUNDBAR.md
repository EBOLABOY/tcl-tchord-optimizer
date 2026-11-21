# TCL Q95K 11.1.4 旗舰回音壁逆向工程与 HDMI-CEC T-Symphony 协议分析

## 1. 硬件平台与操作系统（实机遥测证实）
* **硬件平台**：MediaTek MT8532 四核 Cortex-A7（`aud8532p1-emmc-c4a-mt7921`）+ MT7921 Wi-Fi 6 / BT
* **声学配置**：11.1.4 物理全景声系统，共 **22 个物理发声单元**（含独立无线后环绕与**双 7 吋推挽式无线低音炮**）
* **操作系统与中间件**：Linux 6.1 + StreamUnlimited **StreamSDK `26.02-Gallium-86-g13e1976`**
* **DSP 引擎**：瑞士 **Illusonic DSP**（`settings:/illusonic/soundbarType = 13`，`initialConfigName = "soundbar_startup.txt"`）
* **网络暴露面与安全边界**：
  * 开放 TCP 端口：`7000`（AirPlay）、`8043`（StreamSDK HTTPS CM API）、`8080`（HTTP 跳转 `/webclient/` -> 404）；无 SSH / Telnet / ADB。
  * **访问控制边界**：`settings:/webserver/authMode = "setData"` —— `getData` / `getRows` 只读遥测对局域网开放，`setData` 写接口返回 `401 Unauthorized`。本工具严格遵守此认证边界，仅对 `:8043` 执行只读遥测，不尝试任何认证绕过。

---

## 2. StreamSDK 只读音频节点实测清单 (`https://192.168.100.133:8043`)

| StreamSDK 节点路径 | 实测值 / 结构 | 工程意义 |
| :--- | :--- | :--- |
| `settings:/version` | `"26.02-Gallium-86-g13e1976"` | 回音壁 StreamSDK 固件版本 |
| `settings:/illusonic/soundbarType` | `13` | Q95K 11.1.4 物理扬声器阵列配置 ID |
| `settings:/illusonic/initialConfigName` | `"soundbar_startup.txt"` | Illusonic 启动声学矩阵文件 |
| `settings:/imx8AudioFramework/lipSyncConf` | `0` (ms) | 回音壁内部唇音延时（为 `0` 时与 T和弦原生时延表对齐） |
| `settings:/system/audioOutputDelay` | `[{"delayUs": 0, "sampleRate": 0}]` | 微秒级输出补偿延时 |
| `settings:/imx8AudioFramework/dacConf` | `numChannels=8, routeMap="1,2,27,28,19,20,3,4,..."` | 主条形音箱 8 路 DAC 通道映射（其余由无线链路驱动环绕/低音炮） |
| `settings:/imx8AudioFramework/lpcmConf` | `"-pcmchmap#1,2,3,4,27,28,19,20"` | LPCM 多声道输入映射 |
| `settings:/imx8AudioFramework/dolby/dolbyAudioProcValues` | `01-off`, `02-movie`, `03-music`, `04-night` | 杜比处理模式枚举 |
| `settings:/mediaPlayer/volumeMap` | 101 级对数音量曲线（`vol=8` -> `-62.0 dB`） | 精确反映回音壁当前实际声压衰减 |
| `settings:/mediaPlayer/equalizerOnOff` / `postprocessing` | `True` / `True` | 内置均衡与后处理激活状态 |
| `settings:/mediaPlayer/bass` / `treble` / `loudness` | `0` / `0` / `False` | 音调与响度补偿状态 |
| `powermanager:target` | `networkStandby` / `online` | 电源状态 |

---

## 3. Q95K 与电视端 HDMI-CEC「TCL-Ready (TRD) / T-Symphony (T和弦)」完整协议逆向

虽然无法直接提取 Q95K 内部只读固件二进制，但通过 REA + `baksmali` 完整逆向电视侧 `/apex/com.tcl.apex.tvinput/javalib/com.tcl.hdmi-service.jar`（`TclReady`、`TclTSymphonyHandShakeAction`、`TclRequestTSymphonyLatencyDataAction`、`TclReadyRequestCurrentDeviceInfoAction`）、`/apex/com.tcl.tcore/javalib/tcl-framework.jar`（`TclHdmiTvClient`）以及 `/apex/com.tcl.tcore/lib64/hw/audio.tcl.default.so`（`fpi_audio_set_sbar_latency`、`fpi_audio_set_tcl_sbar_name`），我们完整还原了 Q95K 的双向 HDMI-CEC 控制与时延协商协议：

### 3.1 CEC 物理标识
* 逻辑地址：`0x05`（Audio System），物理地址：`0x1000`（HDMI 1 eARC，实机 `mEarcStatus=3`）
* OSD 名称：`TCL Q95K`
* **TRD Vendor ID**：`0x4A688D`（十进制 `4876429`，Q95K 实机使用）与 `0x74636C`（十进制 `7627628`，ASCII `"tcl"`）
* 传输载体：HDMI-CEC **`Vendor Command With ID`（Opcode `0xA0`）**，前 3 字节为 Vendor ID，第 4 字节（`params[3]`）为 TCL 私有操作码。

### 3.2 T-Symphony (T和弦) 握手与出厂实测时延表交换（关键结论）
1. **三步 TRD 握手（`TclTSymphonyHandShakeAction`）**：
   * `0x10`（TV 握手请求） -> `0x11`（Q95K 回复 TRD 协议版本 `mSbarTrdVersion`）
   * `0x12`（TV 请求能力描述符） -> `0x13`（Q95K 上报支持的 EQ 模式与 TRD 能力位）
   * `0x16`（TV 请求 T-Symphony 状态） -> `0x17`（Q95K 确认支持 T和弦，电视端置 `sys.tcl.tsymphony.mode=1`）
2. **T和弦激活与实测时延表上报（`TclRequestTSymphonyLatencyDataAction`）**：
   * TV 下发 `0x18`（Set T-Symphony Mode Status） -> Q95K 回复 `0x19`（成功） -> TV 立即下发 **`0x1A`（Audio Latency Request）**。
   * **Q95K 连续回复 3 帧 `0x1B`（T-Symphony Audio Latency Report）**，每帧携带 8 字节载荷 = 2 个 32-bit 打包整数，每个 32-bit 打包整数包含 **2 组 `(4-bit 音频格式编号, 12-bit 毫秒时延)`**：
     ```text
     bits [31:28] = format1 (0..11)    bits [27:16] = latency1_ms (0..4095)
     bits [15:12] = format2 (0..11)    bits [11:0]  = latency2_ms (0..4095)
     ```
   * 实机 `settings get system tcl_sys_audio_system_option_type_16393` 读得 `-1332805632` = `0xB08F0000` -> 解码得格式 `0xB`（DTS:X）= **`143 ms`**！
   * 反汇编 `audio.tcl.default.so` 中的 `fpi_audio_set_sbar_latency`（`0x3f940`）证实：TCL 仅对 `"TCL S45H"` / `"TCL S55H"` 做了 74ms/150ms 的硬编码补丁；**对 `"TCL Q95K"` 完全透传回音壁上报的出厂实测时延**。
   * **结论**：严禁像 v2.x 那样盲目覆写 `AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY`，保留 Q95K 原生 CEC `0x1B` 协商时延表才能保证各编码器精确对齐！

### 3.3 完整 Q95K TRD CEC Vendor Opcode 对照表（`TclReady.smali`）
| TV -> Q95K (请求/设置) | Q95K -> TV (上报/回复) | 功能说明 |
| :--- | :--- | :--- |
| `0x10` | `0x11` | TRD 握手与协议版本协商（1.0 / 2.0 / 2.1） |
| `0x12` | `0x13` | 请求 / 上报回音壁 TRD 能力描述符与 EQ 列表 |
| `0x14` | `0x15` / `0x28` | 设置 / 上报回音壁 EQ 模式（Standard/Movie/Music/Voice/Game/Sport/Night/Custom） |
| `0x16` / `0x18` | `0x17` / `0x19` | T-Symphony (T和弦) 能力查询与开关同步 |
| `0x1A` | `0x1B` (×3帧) | **请求 / 上报全编码器出厂实测时延表** |
| `0x1C` / `0x1E` | `0x1D` | 查询 / 设置 T-Symphony 用户自定义时延（`setUserLatency`） |
| `0x1F` / `0x21` | `0x20` | 查询 / 设置总音量增益（`setTotalVolumeGain`） |
| `0x23` | - | 设置声音曲线（`sendSetSoundCurveMessage`） |
| `0x25` | `0x26` | 同步 AIAQ 模式（`setAiaqMode`） |
| `0x29` | `0x2A` | 查询 / 上报当前完整设备状态（6 项位掩码聚合上报） |
| `0x2B` / `0x2E` / `0x31` / `0x34` / `0x37` / `0x3A` / `0x3D` | `0x2C..0x3F`, `0x48` | 夜间模式 / 低音增强 / 虚拟环绕 / 对白增强 / 清晰度 / 后环绕音量 / AI-SONIC |
| `0x40` | `0x41` / `0x42` | 重置回音壁音效设置 |
| `0x46` | `0x47` | 查询 / 上报回音壁型号类型（`mSoundbarType`）与版本号 |
| `0x49` | `0x50` / `0x51` | BeoSonic 声场坐标（x/y 轴） |
| `0x52` / `0x54` | `0x53` / `0x55` | 品牌代码与自定义控制能力位 |

本工具的 `AudioTool query_soundbar_cec`（集成在 `--diagnose` 中）通过电视侧合法的 `android.hardware.hdmi.TclHdmiTvClient` 接口直接读取上述 Q95K 实时状态。
