# TCL Q95K 11.1.4 旗舰回音壁逆向工程分析

## 1. 硬件平台与操作系统
* **硬件平台**：MediaTek MT8532 四核 Cortex-A7（`aud8532p1-emmc-c4a-mt7921`）
* **无线模组**：MediaTek MT7921 Wi-Fi 6 / Bluetooth Combo
* **内核版本**：`Linux version 6.1.0-mainline (oe-user@oe-host) (arm-poky-linux-gnueabi-gcc 13.2.0) #1 SMP PREEMPT Thu Sep 17 11:28:40 UTC 2026`
* **设备容器标识**：`cortexa7container-c6036b68-c399-45ac-8036-bb70ae758608`
* **OEM 厂商**：GSD Vietnam Technology Co. (TCL 越南智能声学智造基地，MAC OUI: `CC:61:46`)

---

## 2. 软件栈架构与 Illusonic DSP 引擎

### 2.1 StreamUnlimited StreamSDK
Q95K 回音壁搭载了国际发烧级音响通用的 **StreamUnlimited StreamSDK v26.02-Gallium**（常见于 Sennheiser AMBEO、Arcam、Mark Levinson 等顶尖设备）。

### 2.2 Illusonic 物理声学配置
* 位于 `settings:/illusonic` 命名空间：
  * `settings:/illusonic/initialConfigName`: `"soundbar_startup.txt"`
  * `settings:/illusonic/soundbarType`: `13`（对应 Q95K 11.1.4 物理扬声器阵列定义）

---

## 3. 本地 REST API 控制规格

回音壁在局域网内开放 HTTPS `8043` 和 HTTP `8080` 端口，提供 Configuration Manager (CM) 本地 JSON API：

### 3.1 核心 API 端点
* **节点读取 (`getData`)**：
  ```http
  GET https://<soundbar-ip>:8043/api/getData?path=<node_path>&roles=@all&_nocache=<ts>
  ```
* **节点写入 (`setData`)**：
  ```http
  POST https://<soundbar-ip>:8043/api/setData
  Content-Type: application/json

  {
    "path": "player:volume",
    "role": "value",
    "value": {"type": "i32_", "i32_": 15}
  }
  ```
* **容器行枚举 (`getRows`)**：
  ```http
  GET https://<soundbar-ip>:8043/api/getRows?path=<container_path>&roles=@all&from=0&to=100
  ```

### 3.2 关键音频节点清单
* `settings:/imx8AudioFramework/lipSyncConf`：唇音同步时延（可调范围 0–500 ms）。
* `settings:/system/audioOutputDelay`：硬件微秒级输出延迟（格式：`systemAudioDelay`）。
* `settings:/imx8AudioFramework/dacConf`：DAC 多声道输出配置（8 通道主板输出总线）。
* `settings:/imx8AudioFramework/cecEnabled`：HDMI-CEC 控制链路开关。
* `player:volume`：主音量（范围 0–100）。
* `settings:/mediaPlayer/mute`：静音开关。
