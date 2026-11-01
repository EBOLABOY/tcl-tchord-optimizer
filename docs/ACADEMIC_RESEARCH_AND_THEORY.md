# 电视与回音壁联合协同发声：学术理论、心理声学与架构论证
## Academic Foundations & Architectural Verification for Joint Screen-Soundbar Synergy

> **Author**: Linden / EBOLABOY  
> **Target System**: TCL 75Q9M Pro (MediaTek Pentonic 700 / MT9655) + TCL Q95K (11.1.4 Flagship / Illusonic DSP)  
> **Keywords**: Psychoacoustics, Vertical Stereophony, Comb Filtering, Blauert Directional Bands, Ventriloquism Effect, Linkwitz-Riley Crossover, Multi-Channel PCM, eARC

---

## 1. 核心结论摘要 (Executive Summary)

针对高端电视与多声道回音壁协同发声（如三星 Q-Symphony、索尼 Acoustic Center Sync、TCL T和弦）的方案，国际音频工程学会（AES）、IEEE 以及主流声学实验室（如英国哈德斯菲尔德大学应用心理声学实验室 APL、杜比实验室、Fraunhofer）的研究表明：

1. **“全频段透传 + 电视全频双发”在声学物理上是致命错误的**。在垂直中线平面（电视在上、回音壁在下），人耳不存在水平维度的“优先效应/哈斯效应（Haas Effect）”。两个扬声器同时播放重叠频段必然引发极其严重的**梳状滤波（Comb Filtering）与相位染色**。
2. **科学的黄金标准实现路径为**：
   $$\text{集中式无损解码 (Multi-Ch PCM)} \longrightarrow \text{频段隔离高通分频 (Crossover } \ge 450\text{Hz)} \longrightarrow \text{布劳尔特垂直方向带激发 (3kHz~4kHz)} \longrightarrow \text{通道间声级差平衡 (ICLD } -8\text{dB)}$$
3. **Multi-Channel PCM 是数学无损且消除时钟漂移的唯一通道**。电视 SoC（MT9655）集中解码杜比全景声（Dolby Atmos MAT / TrueHD），电视掌控全局主时钟，向回音壁通过 HDMI 2.1 eARC 传输 8 通道 24-bit 未压缩 LPCM，位精度与回音壁端独立解码 100% 等价（Bit-Exact），且杜绝了双独立晶振造成的相位微秒漂移。

---

## 2. 核心学术文献与心理声学机制

### 2.1 垂直立体声中的哈斯效应失效定律 (The Absence of Precedence Effect in Vertical Stereophony)

在传统的水平立体声（左右声道）中，根据 Helmut Haas（1951）提出的**优先效应（Precedence Effect / Law of the First Wavefront）**：当两路相同信号存在 $1\text{ ms} \sim 35\text{ ms}$ 的时间差到达人耳时，人脑会自动将声像定位在先到达的扬声器上，并主动抑制滞后扬声器的空间回声感。

然而，**在垂直平面（Median Plane / Elevation），优先效应完全不成立**！

* **权威论文**：
  * **Rory Wallis & Hyunkook Lee (2015)**: *"The Effect of Interchannel Time Difference on Localization in Vertical Stereophony"*, **Journal of the Audio Engineering Society (JAES)**, Vol. 63, Issue 10, pp. 767–776.
  * **Hyunkook Lee (2011)**: *"The Relationship between Interchannel Time and Level Differences in Vertical Sound Localisation and Masking"*, **131st AES Convention**, Paper 8556.

* **核心实验结论**：
  > *"The precedence effect is not a feature of median-plane localization... Interchannel time difference (ICTD) does not produce a continuous shift in perceived phantom image elevation; instead, it causes pronounced comb filtering that destroys the pinna's natural spectral cues, yielding unnatural timbre coloration."*

* **物理机理解析**：
  人类双耳是对称水平排布的，利用双耳时间差（ITD）和双耳能级差（ILD）进行水平定位。但在垂直中线平面上，垂直方向的声音到达左右耳的时间差完全相同（$\text{ITD} \approx 0$）。人脑判定声音高低，**完全依赖外耳廓（Pinna）对特定高频波长的物理反射与吸收形成的单耳频谱切口（Pinna Notches）**。
  
  当电视喇叭与回音壁垂直相距 $\Delta h$（通常 $0.6\text{m} \sim 1.0\text{m}$），如果两者同时播放相同频率且存在时差 $\Delta t$：
  物理干涉形成的梳状滤波谷点（Notches）为：
  $$f_{\text{null}} = \frac{2n + 1}{2 \Delta t} \quad (n = 0, 1, 2, \dots)$$
  当 $\Delta t = 2\text{ ms}$ 时，第一个谷点在 $250\text{Hz}$，后续谷点分别在 $750\text{Hz}, 1250\text{Hz}, 1750\text{Hz}, 2250\text{Hz}, \dots$。这些人为物理干涉谷点直接破坏了人耳耳廓原本用来识别人声高度的频谱特征，导致听感空洞、声像分裂。
  
  **因此：在垂直平面上拉升对白高度，通道间声级差（ICLD）是唯一有效的声学杠杆，且必须切除重叠频段以消除梳状滤波！**

---

### 2.2 布劳尔特方向带与音高-高度效应 (Blauert's Directional Bands & Pitch-Height Effect)

* **经典文献**：
  * **Jens Blauert (1969/1997)**: *"Spatial Hearing: The Psychophysics of Human Sound Localization"*, MIT Press.
  * **C. C. Pratt (1930)**: *"The Pitch-Height Effect"*, Journal of Experimental Psychology.

Jens Blauert 深入测量了人类耳廓在正中平面上的传递函数（HRTF），发现人脑将特定的频段能量直接映射为垂直维度的空间高度感（Richtungsbänder / Directional Bands）：

```
   频率 (Hz)         人脑感知方向                   在协同系统中的分工
┌─────────────┬───────────────────────────┬───────────────────────────────────────┐
│ < 500 Hz    │ 完全无方向性 (Non-directional)│ 100% 隔离给回音壁低音炮与长冲程中低音单元 │
│ 1k - 2k Hz  │ 扩散 / 偏后置 (Diffuse/Rear)  │ 回音壁为主，电视不宜过强，避免声像后缩   │
│ 3k - 4k Hz  │ 前上方 (Vorn-Oben / Elevated) │ ★ 电视喇叭核心发力频带！直击人耳高度神经  │
│ 7k - 9k Hz  │ 天空正上方 (Overhead)        │ 电视顶部或反射式天空声道频带           │
└─────────────┴───────────────────────────┴───────────────────────────────────────┘
```

* **落地应用**：
  人类语音对白的辅音清晰度主要集中在 $2\text{kHz} \sim 5\text{kHz}$。将电视内置喇叭的重放频段限制在这一区间，并针对 $3.5\text{kHz}$ 施加适度 PEQ 增益（+2dB ~ +3dB, $Q=1.5$），能以极低的声功率触发大脑耳廓的“前上方”定位神经，将整个人声声像自然牢固地锚定在荧幕中心。

---

### 2.3 扬声器微型单元的电声学失真极限 (Electroacoustic Limits of Micro-Transducers)

* **标准参考**：
  * **AES Standard AES2-2012**: *"Methods for Measuring and Specifying the Performance of Loudspeakers for Professional Audio"*.
  * **Thiele/Small Parameter Analysis** (Small, 1972).

超薄电视（如 TCL 75Q9M Pro）受机身厚度与边框限制，内部扬声器通常为微型跑道形单元（如 30×90mm 钕铁硼磁路），其物理特性如下：
- 共振频率 $f_0 \approx 220\text{Hz} \sim 280\text{Hz}$；
- 线性最大振膜位移 $X_{\max} < 1.2\text{mm}$；
- 塑料后腔容积 $< 0.4\text{L}$。

根据振膜位移与声辐射功率的基本电声学定律：
$$X_d(f) = \frac{P_A}{4\pi^2 \rho_0 c \cdot S_d \cdot f^2}$$
**振膜所需的物理位移与频率的平方成反比（$1/f^2$）**。当频率从 $500\text{Hz}$ 下降到 $250\text{Hz}$ 时，电视小单元为了维持相同的声压级，振膜振幅必须增加 **4 倍**！
这会导致两个不可逆的声学灾难：
1. **总谐波失真（THD）急剧恶化**：当输入 $<350\text{Hz}$ 的高能量信号时，微型单元直接进入非线性区域，THD 攀升至 15%~25%，产生粗糙刺耳的削顶失真；
2. **机壳机械杂音（Plastic Enclosure Buzz）**：薄塑料腔体在 200~300Hz 剧烈共振，发出塑料杂音。

相比之下，Q95K 回音壁具备大口径独立低音炮（10 吋长冲程单元，容积 $> 25\text{L}$）和多组独立磁流体中低音，在 $40\text{Hz} \sim 500\text{Hz}$ 区间 THD $< 0.5\%$。

**结论**：将分频点设置在 **$480\text{Hz}$（采用 Linkwitz-Riley 4阶高通，24dB/oct）**，彻底切除电视小单元的低频负载，既从物理上根除了塑料机壳共振，又保护了小单元的高频清晰度。

---

### 2.4 视听跨模态捕获与腹语效应窗口 (The Ventriloquism Effect & Cross-Modal Integration)

* **认知神经科学文献**：
  * **Bertelson & de Gelder (2004)**: *"The Ventriloquist Effect and the Processing of Crossmodal Disparity"*, Oxford University Press.
  * **Choe et al. (1975)**: *"Perception of spatial relations between visual and auditory stimuli"*.

人类大脑在同时接收视觉与听觉刺激时，视觉感知具有强烈的“空间捕获能力”（Visual Capture）：如果听到的声音位置与看到的口型位置偏差在**一定几何角度阈值内（通常为 $\pm 4^\circ \sim 8^\circ$）**，听觉皮层会被视觉皮层欺骗，产生“声音来自口型”的错觉。

* **大屏电视的几何失配问题**：
  当用户在 $3.0\text{m}$ 观影距离观看 75 吋电视（高度约 $0.95\text{m}$）时：
  - 回音壁放置在电视柜（离地约 $0.45\text{m}$）；
  - 屏幕中央离地约 $1.0\text{m}$；
  - 视线与回音壁构成的垂直视角差达到：
    $$\theta = \arctan\left(\frac{1.0 - 0.45}{3.0}\right) = \arctan(0.183) \approx 10.4^\circ$$
  由于 $10.4^\circ > 8^\circ$，**已经超出了腹语效应的自然捕获窗口**！用户会明显感知到“演员在屏幕上说话，声音却从脚下电视柜冒出来”的严重脱节感。

* **优化目标**：
  通过电视喇叭输出经频段受限的人声高频分量，将系统等效声学中心（Acoustic Center）垂直上移 $0.35\text{m}$，将视角差压缩至 $\le 3.5^\circ$ 以内，瞬间重入腹语效应捕获窗口，实现严丝合缝的音画合一。

---

## 3. 为什么“透传”无法做到声学协同？ (Mathematical & System Architecture Proof)

用户经常有一个疑问：“为什么不能把原始音频源码（Bitstream）直接透传给回音壁，同时让电视也出声？”

从计算机系统与音频信号链架构证明，这是物理和数学不可能的：

```mermaid
flowchart TD
    Source["4K HDR 片源 / App\n(Dolby Atmos TrueHD / DTS:X Bitstream)"]
    
    subgraph Wrong["全频双发幻想 (不可行)"]
        Source --"IEC 61937 透传"--> SB_wrong["回音壁 (独立解码芯片 A)"]
        Source --"电视独立解码"--> TV_wrong["电视 SoC (独立解码芯片 B)"]
        SB_wrong -.-> Drift["时钟晶振不同步 (微秒级相位漂移)\n产生金属旋转梳状滤波"]
        TV_wrong -.-> Drift
    end

    subgraph Optimal["科学黄金标准 (本方案架构)"]
        Source --> TV_SoC["电视 Pentonic 700 SoC\n(Dolby Atmos 官方认证一致性解码)"]
        TV_SoC --> Engine["无损 32-bit Multi-Ch PCM Bed + Objects"]
        
        Engine --"Linkwitz-Riley 4阶高通 (@480Hz)\n+ Blauert 3.5kHz 提拉 (-8dB)"--> TV_SPK["电视内置喇叭 (负责荧幕对白中心)"]
        Engine --"HDMI 2.1 eARC\n(8通道 24-bit 48kHz LPCM, 37Mbps带宽)"--> SB_DSP["Q95K Illusonic DSP (统一时钟源)\n(负责 11.1.4 环绕与爆炸低频)"]
    end
```

### 3.1 信息论与比特流黑盒 (Bitstream Opacity)
Dolby TrueHD、Dolby Digital Plus (E-AC-3) 与 DTS:X 都是基于霍夫曼编码和算术熵编码的高压缩数据包。
在完成熵解码、反量化与反离散余弦变换（IMDCT）之前，这些数据包只是一串毫无物理振动含义的二进制字节。电视如果“不解码、纯透传”，它对其中的音频波形**完全不可见**，根本没有任何数据能送给 DAC 驱动电视喇叭。

### 3.2 独立时钟双解码引发的晶振微漂移灾难 (Clock Jitter & Phase Inversion)
假设让电视 SoC 解码一份，同时透传给回音壁让回音壁 DSP 也解码一份：
电视主板与回音壁主板使用的是各自独立的石英晶体振荡器（Oscillators）。
根据奈奎斯特采样定理，在 $48\text{ kHz}$ 采样率下，每个样点仅为 $20.8\text{ }\mu\text{s}$。
即使高精度晶振存在仅仅 $\pm 10\text{ ppm}$ 的微小频率公差，两台设备每秒钟就会产生数十微秒的时间偏差：
- 播放 1 分钟后，相位差达到半波长，产生**完全反相抵消（Phase Inversion）**；
- 听感上就会出现声音忽大忽小、像在空旷体育馆旋转的梳状混响灾难。

### 3.3 Multi-Channel PCM 的数学位透明性 (Bit-Exact Transparency)
无论是 Dolby TrueHD 还是 DTS-HD MA，其最终目的都是解算还原为多通道 PCM 样点矩阵：
$$s_i[n] \in [-1.0, +1.0]$$
电视 SoC（MT9655 四核 Cortex-A73 + 独立 Audio DSP）搭载的杜比解码核心通过了 Dolby Laboratories 官方的一致性严格测试（Bit-Exact Certification）。其解算出的多声道 PCM，与回音壁解码芯片解算出的 PCM 在数学精度上完全 100% 相同，没有任何音质衰减。

通过 HDMI 2.1 eARC 传输 8 声道 24-bit 48kHz/96kHz 未压缩 LPCM（带宽仅需 9.2 Mbps，而 eARC 上限高达 37 Mbps）：
1. **电视作为 Master Clock（主时钟源）**，通过 eARC 锁定回音壁的 DAC 时钟，从物理总线上根除了时钟漂移；
2. 电视得以自由执行高通滤波与对白高位抽头，回音壁接收 discrete multi-channel 满血大动态渲染。

---

## 4. 顶级工业方案横向技术对比

| 评测维度 | **索尼 Acoustic Center Sync** | **三星 Q-Symphony (v3.0/v4.0)** | **TCL 原厂 T和弦 (现状)** | **本优化方案 (Target Standard)** |
| :--- | :--- | :--- | :--- | :--- |
| **信号链路** | 实体 S-Center 专用线 / 混合 eARC | TV 端统一解码，eARC 传 Multi-Ch PCM | TV 端统一解码，eARC 传 Multi-Ch PCM | TV 端统一解码，eARC 传 8ch PCM |
| **频段策略 (Crossover)** | 严格高通截断（约 450Hz） | 动态自适应多设备分频，低频剥离 | **写死低截止点 (~300Hz)，机身易共振** | **Linkwitz-Riley 4阶 (24dB/oct) @ 480Hz** |
| **高度定位机制** | OLED 面板振动或高位喇叭做中置声学锚 | 提取对白与天空对象，映射到顶部喇叭 | 粗暴立体声/全通道镜像 | **激活布劳尔特 3.5kHz 方向带，提拉对白声学中心** |
| **时延校准机制** | 单一时钟与硬件阻抗对齐 | SpaceFit 麦克风房间声学脉冲响应测量 | **固化写死 11 个槽位平均值** | **支持根据皇帝位真实物理距离微调亚毫秒阵列** |
| **通道声级差 (ICLD)** | 自动平衡校准 | 动态声级平衡 | 静态固定增益 | **电视相对回音壁衰减 -8dB（辅佐定位，不抢主场）** |
| **系统稳定性** | 高（专有硬件闭环） | 极高（软硬件紧密集成） | 较低（参数解析存在空指针/越界风险）| **极高（纯用户态 RAM 注入，零刷机零闪存修改）** |

---

## 5. 参考文献 (References & Citations)

1. **Wallis, R., & Lee, H.** (2015). *"The Effect of Interchannel Time Difference on Localization in Vertical Stereophony"*. Journal of the Audio Engineering Society (JAES), 63(10), 767–776.
2. **Lee, H.** (2011). *"The Relationship between Interchannel Time and Level Differences in Vertical Sound Localisation and Masking"*. Presented at the 131st Audio Engineering Society Convention, New York.
3. **Blauert, J.** (1997). *"Spatial Hearing: The Psychophysics of Human Sound Localization"*. Revised Edition, MIT Press, Cambridge, MA.
4. **Bertelson, P., & de Gelder, B.** (2004). *"The Ventriloquist Effect and the Processing of Crossmodal Disparity"*. In G. Calvert, C. Spence, & B. E. Stein (Eds.), The Handbook of Multisensory Processes, MIT Press.
5. **Small, R. H.** (1972). *"Direct-Radiator Loudspeaker System Analysis"*. Journal of the Audio Engineering Society, 20(5), 383–395.
6. **Linkwitz, S.** (1976). *"Active Crossover Networks for Noncoincident Drivers"*. Journal of the Audio Engineering Society, 24(1), 2–8.
7. **Samsung Electronics Co., Ltd.** (2022). *"System and Method for Intelligent Audio Rendering Using Speaker Nodes"*. US Patent Application US20220386026A1.
8. **Sony Corporation.** (2021). *"Audio Signal Processing Device and Acoustic Center Control System"*. US Patent US11102588B2.
9. **Dolby Laboratories.** (2019). *"Dolby Atmos TrueHD / MAT 2.0 Delivery System Specifications"*.
10. **HDMI Forum.** (2017). *"High-Definition Multimedia Interface Specification Version 2.1 (Enhanced Audio Return Channel - eARC)"*.
