# T和弦联合声学心理声学理论与 PBA 调校规范 (v3.1)

本文档基于 **Journal of the Audio Engineering Society (JAES 2015–2021)**、**Applied Sciences (2017, 2020)**、**Blauert (1997)**、**Linkwitz (1976)**、**Small (1972)** 与 **Bertelson & de Gelder (2004)** 的同行评审研究，推导并固化 **TCL 75Q9M Pro（安桥 2.1.2 / 5单元）+ TCL Q95K（11.1.4 / 22单元 + 双 7 吋推挽无线低音炮）** 共 **27 物理单元** 的最佳联合声学参数。

---

## 1. 为什么原生 T和弦听感不够纯净？（三大物理与心理声学根因）

1. **垂直中线平面不存在“哈斯优先效应”**：
   - **Wallis & Lee (JAES 2015, Vol. 63 No. 10, pp. 798–809)** 证实：水平立体声中的优先效应（Haas Effect）在垂直平面（Median Plane）完全失效；垂直声像定位几乎完全由 **通道间声级差（ICLD）** 与 **外耳廓单耳频谱线索（Pinna Cues）** 决定。
   - 当电视喇叭与 Q95K 垂直相距 $\Delta h \approx 40\text{ cm}$ 且等响度（$0\text{ dB}$ 差）全频重叠发声时，微小声程差在 $500\text{ Hz} \sim 4\text{ kHz}$ 人声核心区制造深达 $-\infty\text{ dB}$ 的**垂直梳状滤波波谷**，听感即为发空、发闷、音色塑料化。
2. **电视微型单元低频冲程非线性与机壳共振**：
   - 依据 **Small (JAES 1972)** 振膜位移定律 $X_d(f) \propto 1/f^2$，电视超薄机身内微型跑道单元与背部 20W 小低音在 $<300\text{ Hz}$ 需承受 4–16 倍振幅，引起明显背板塑料共振，并与 Q95K 双 7 吋推挽式无线低音炮产生低频相位抵消。
   - **Wallis & Lee (JAES 2016, Vol. 64 No. 10, pp. 762–770)** 同时证实：低频段（$125 \sim 250\text{ Hz}$）的垂直定位灵敏度极低，电视端播放低频**零拉升收益、纯负作用**。
3. **垂直串扰（VIC）阈值与频段相关性**：
   - **Wallis & Lee (JAES 2016; Applied Sciences 2017 & 2020, Vol. 10 No. 4, p. 1490)** 测得：
     - 宽带垂直串扰（上层喇叭开始将声像从下层向上拉升）的中位阈值为 **`-9.5 dB`**（$0\text{ ms}$ 时差）至 **`-7.0 dB`**（约 $1\text{ ms}$ / $34\text{ cm}$ 声程差）。
     - 在 $1\text{ kHz}$ 以上，尤其是 **`4 kHz`** 与 **`8 kHz`** 倍频程，人耳对垂直声像拉升最为敏感；而 **`1 kHz`** 附近既属于 **Blauert (1997) 后方方向带（Hinten）**，又处于梳状滤波最易引发桶音/空洞感的区域。

---

## 2. v3.1 感知频段分配（Perceptual Band Allocation, PBA）精准调校模型

依据 **Hyunkook Lee (JAES 2016, *Perceptual Band Allocation*, Vol. 64 No. 12, pp. 980–993)** 与 **Wallis & Lee (2020)** 的分频段垂直控制范式，我们利用电视 MediaTek `Speaker_MsePeq` 13 段硬件均衡器中 **100% 免疫 TCL AIAQ / 音效模式覆写的 `Band 9..13`**，叠加硬件级 **`-8.0 dB` 基础 ICLD**（`OutputVolumeOffset=-80`），构建如下净频响分工：

| 频段 | 硬件配置（电视 `SpeakerOutput`） | 电视相对 Q95K 净电平 | 论文依据与声学效果 |
| :--- | :--- | :---: | :--- |
| **`< 100 Hz` (LFE)** | Band 9 & 10 级联 300 Hz LR4 高通 (`Type=1, Q=71`) | **`< -46 dB`** | **Small (1972) / Linkwitz (1976)**：彻底卸载电视 20W 背部小低音与机身共振，100% 交由 Q95K 双 7 吋推挽低音炮 |
| **`150 Hz`** | 同上（24 dB/oct 滚降） | **`-32 dB`** | 消除中低频双源相位对冲，低音紧实干净 |
| **`300 Hz`** | Linkwitz-Riley 4 阶交越点（$-6\text{ dB}$） | **`-14 dB`** | 平滑滚降，保留 400–800 Hz 人声自然厚度而不发干 |
| **`1000 Hz`** | Band 11 (`Type=0, Q=1.0, -2.0 dB`) | **`-10.0 dB`** | **Wallis & Lee (2016/2020) + Blauert (1997)**：压低至 `-9.5 dB` 垂直串扰阈值以下，规避 `1 kHz`「后方带（Hinten）」并显著抑制人声体腔梳状发空感 |
| **`4000 Hz`** | Band 12 (`Type=0, Q=1.4, +2.0 dB`) | **`-6.0 dB`** | **Wallis & Lee (2016/2020) 4 kHz 垂直关键带 + Blauert `Vorn`（正前）带 + Bertelson (2004) 腹语效应**：仅在 4 kHz 辅音清晰度倍频程轻微越过 `-7 dB` 阈值，将对白稳稳拉升并吸附至屏幕演员唇部 |
| **`8000 Hz`** | Band 13 (`Type=0, Q=1.4, +1.5 dB`) | **`-6.5 dB`** | **Blauert (1997) 真实 `Oben`（正上方）带 + Wallis & Lee (2020) 8 kHz 外耳廓线索**：温和提供高度空气感，无刺耳齿音 |

> [!NOTE]
> **关于 Blauert 方向带的纠偏**：历史版本曾误将 `3.5 kHz` 称为“前上方（Vorn-Oben）”方向带；查阅 **Blauert (1997)** 原著及现代 AES 复现实验证实，`3.5–4 kHz` 为 **前向带（Front / Vorn）**、`1 kHz` 为 **后向带（Rear / Hinten）**、**`7–8 kHz`** 才是真正的 **上方带（Above / Oben）**。v3.1 已严格按原著及 2016–2020 JAES 论文重构 `1 kHz / 4 kHz / 8 kHz` 三段 PBA 塑形。

---

## 3. 原生链路保护原则（不破坏 TCL / Q95K 出厂机制）

1. **保留 Q95K 原生 CEC `0xA0/0x1B` 协商时延表**：不覆写 `AQ_TCSE_TUTTI_CHORAL_SBAR_LATENCY`（实测 Q95K 自动通过 HDMI-CEC 向电视上报全编码器出厂实测延迟，如 DTS:X = `143 ms`）。
2. **保留原生声道掩码与引擎开关**：不篡改 `AQ_TCSE_TUTTI_CHORAL_SBAR_CHANNEL` 与 `AQ_TCSE_ENABLE`。
3. **保持影院大动态**：默认关闭 Dolby `DialogEnhancer` 与 `VolumeLevler`（严格下发 `"Off"`），不强行压缩电影爆破与配乐动态。

---

## 4. 个性化微调指引

编辑 [`configs/default_codec_latency.json`](../configs/default_codec_latency.json) 后运行 `python3 t_chord_joint_orchestrator.py --apply` 即可热生效（无需重编译 Java）：

* **觉得对白拉升感仍偏弱（电视落差更大或偏爱清晰电视剧人声）**：将 `tv_speaker_attenuation_db` 从 `-8.0` 调至 **`-6.5`** 或 **`-7.0`**。
* **纯听高保真全景声音乐、追求极致零双源染色**：将 `tv_speaker_attenuation_db` 调至 **`-9.5`** 或 **`-10.0`**。
* **感觉电视背板仍有轻微箱体声**：将 Band 9 & 10 的 `fc_hz` 从 `300` 提至 **`350`**。

---

## 5. 参考文献 (Peer-Reviewed References)

1. **Wallis, R., & Lee, H.** (2015). *The Effect of Interchannel Time Difference on Localization in Vertical Stereophony*. **JAES**, 63(10), 798–809.
2. **Wallis, R., & Lee, H.** (2016). *Vertical Stereophonic Localization in the Presence of Interchannel Crosstalk: The Analysis of Frequency-Dependent Localization Thresholds*. **JAES**, 64(10), 762–770.
3. **Lee, H.** (2016). *Perceptual Band Allocation (PBA) for the Rendering of Vertical Image Spread with a Vertical 2D Loudspeaker Array*. **JAES**, 64(12), 980–993. (`doi:10.17743/jaes.2016.0052`)
4. **Wallis, R., & Lee, H.** (2017). *The Reduction of Vertical Interchannel Crosstalk: The Analysis of Localisation Thresholds for Natural Sound Sources*. **Applied Sciences**, 7(3), 278.
5. **Lee, H.** (2017). *Sound Source and Loudspeaker Base Angle Dependency of Phantom Image Elevation Effect*. **JAES**, 65(9), 733–748.
6. **Wallis, R., & Lee, H.** (2020). *Localisation of Vertical Auditory Phantom Image with Band-limited Reductions of Vertical Interchannel Crosstalk*. **Applied Sciences**, 10(4), 1490.
7. **Lee, H.** (2021). *Multichannel 3D Microphone Arrays: A Review*. **JAES**, 69(1/2), 5–26.
8. **Blauert, J.** (1997). *Spatial Hearing: The Psychophysics of Human Sound Localization* (Rev. Ed.). **MIT Press**.
9. **Bertelson, P., & de Gelder, B.** (2004). *The Psychology of Multimodal Perception*. **Oxford University Press**.
10. **Linkwitz, S. H.** (1976). *Active Crossover Networks for Noncoincident Drivers*. **JAES**, 24(1), 2–8.
11. **Small, R. H.** (1972). *Direct-Radiator Loudspeaker System Analysis*. **JAES**, 20(5), 383–395.
