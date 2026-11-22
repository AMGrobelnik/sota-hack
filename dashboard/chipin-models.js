/*
 * chipin-models.js: pure functions and sourced constants for the ChipIn
 * dashboard. No dependencies, no DOM access. Defines window.ChipInModels in a
 * browser and module.exports in Node.
 *
 * Conventions
 *   - Power in microwatts (uW), energy in milliwatt-hours (mWh), current in mA.
 *   - Every figure carries a kind: "datasheet" (read from the maker's sheet),
 *     "measured", "estimate" (our own model or lab estimate) or "assumed"
 *     (from a search snippet, a vendor copy, or an assumed supply voltage or
 *     duty cycle). Nothing assumed is presented as a datasheet figure.
 *   - Cost figures are all illustrative: there are no sourced cost figures.
 */
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ A.
  // Confidence

  /** Wilson score interval for k successes out of n trials. */
  function wilson(k, n, z) {
    if (z === undefined) z = 1.96;
    if (!(n > 0)) return { low: 0, high: 1 };
    k = Math.max(0, Math.min(k, n));
    var p = k / n;
    var z2 = z * z;
    var denom = 1 + z2 / n;
    var centre = (p + z2 / (2 * n)) / denom;
    var half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom;
    var low = k === 0 ? 0 : Math.max(0, centre - half);
    var high = k === n ? 1 : Math.min(1, centre + half);
    return { low: low, high: high };
  }

  /*
   * Confidence headline. The width judged is the Wilson interval width at an
   * observed rate of 50 percent (the widest case) for the SMALLER of the
   * positive and negative counts, since the rarer class limits how precisely
   * either sensitivity or specificity is known.
   *   width > 0.10            -> low
   *   0.05 < width <= 0.10    -> medium
   *   width <= 0.05           -> high
   * Fewer than 10 distinct patients is always low (results may reflect a few
   * people rather than a population).
   */
  var CONFIDENCE_THRESHOLDS = {
    low_if_width_above: 0.1,
    medium_if_width_above: 0.05,
    low_if_patients_below: 10,
    rate_assumed: 0.5,
    rule:
      "Width of the 95% Wilson interval at a 50% rate for the rarer class: " +
      "above 0.10 is low, above 0.05 is medium, otherwise high; fewer than " +
      "10 patients is always low.",
  };

  function fmtInt(x) {
    return Math.round(x).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function confidenceHeadline(o) {
    o = o || {};
    var pos = o.positives || 0;
    var neg = o.negatives === undefined ? Infinity : o.negatives;
    var rarer = Math.min(pos, neg);
    var rarerName = pos <= neg ? "positive" : "negative";
    var n = Math.round(rarer);
    var iv = wilson(Math.round(n * CONFIDENCE_THRESHOLDS.rate_assumed), n);
    var width = iv.high - iv.low;
    var level;
    if (width > CONFIDENCE_THRESHOLDS.low_if_width_above) level = "low";
    else if (width > CONFIDENCE_THRESHOLDS.medium_if_width_above) level = "medium";
    else level = "high";
    var fewPatients =
      o.patients !== undefined && o.patients < CONFIDENCE_THRESHOLDS.low_if_patients_below;
    if (fewPatients) level = "low";
    var label = level.charAt(0).toUpperCase() + level.slice(1);
    var text = fewPatients
      ? label + ": " + fmtInt(o.patients) + " patients in the test set"
      : label + ": " + fmtInt(n) + " " + rarerName + " cases in the test set";
    return {
      level: level,
      text: text,
      width: width,
      count: n,
      thresholds: CONFIDENCE_THRESHOLDS,
    };
  }

  function asInterval(x) {
    if (x && typeof x.low === "number" && typeof x.high === "number") return x;
    if (x && typeof x.k === "number" && typeof x.n === "number") return wilson(x.k, x.n);
    throw new Error("cannotTellApart needs {low, high} or {k, n}");
  }

  /** True when the two designs' 95% intervals overlap. */
  function cannotTellApart(a, b) {
    var A = asInterval(a);
    var B = asInterval(b);
    var overlap = A.low <= B.high && B.low <= A.high;
    var text = overlap
      ? "These two designs cannot be told apart on this test set: their ranges overlap."
      : "These two designs differ on this test set: their ranges do not overlap.";
    return { overlap: overlap, text: text };
  }

  // ------------------------------------------------------------------ B.
  // Device power. Every figure with its source line.

  var PARTS = [
    {
      id: "max30003",
      name: "ECG front end MAX30003 (1 lead)",
      power_uw: 180,
      per: "per lead (one part per lead)",
      source_name: "MAX30003 datasheet (Analog Devices)",
      source_url: "https://cdn.sparkfun.com/assets/c/7/7/1/0/MAX30003.pdf",
      quote: "ECG channel supply current IAVDD+IDVDD 100 uA at 1.8 V (100 uA x 1.8 V = 180 uW)",
      kind: "datasheet",
    },
    {
      id: "ad8232",
      name: "ECG front end AD8232 (1 lead)",
      power_uw: 510,
      per: "per lead (one part per lead)",
      source_name: "AD8232 datasheet (Analog Devices)",
      source_url: "https://cdn.sparkfun.com/datasheets/Sensors/Biometric/AD8232.pdf",
      quote: "Low supply current: 170 uA (typical); 3 V supply assumed (170 uA x 3 V = 510 uW)",
      kind: "assumed",
    },
    {
      id: "ads1299",
      channels: 8,
      role: "eeg-budget",
      eeg_named: true,
      noise_uvpp: 1,
      noise_note: "1 uVpp (70 Hz bandwidth), ADS1299 datasheet feature list",
      name: "EEG front end ADS1299 (8 channels)",
      power_uw: 39000,
      per: "whole part (8 channels)",
      source_name: "ADS1299 datasheet (Texas Instruments)",
      source_url: "https://www.ti.com/document-viewer/ADS1299/datasheet/specifications",
      quote: "Power dissipation (analog supply 5 V, bias amplifiers off), normal mode 39 / 42 mW typ/max",
      kind: "datasheet",
    },
    {
      id: "ads1299-6",
      channels: 6,
      role: "eeg-budget",
      eeg_named: true,
      noise_uvpp: 1,
      noise_note: "1 uVpp (70 Hz bandwidth), ADS1299 datasheet feature list",
      name: "EEG front end ADS1299-6 (6 channels)",
      power_uw: 30000,
      per: "whole part (6 channels)",
      source_name: "ADS1299 datasheet (Texas Instruments)",
      source_url: "https://www.ti.com/document-viewer/ADS1299/datasheet/specifications",
      quote: "ADS1299-6 normal mode 30 / 33 mW typ/max",
      kind: "datasheet",
    },
    {
      id: "ads1299-4",
      channels: 4,
      role: "eeg-budget",
      eeg_named: true,
      noise_uvpp: 1,
      noise_note: "1 uVpp (70 Hz bandwidth), ADS1299 datasheet feature list",
      name: "EEG front end ADS1299-4 (4 channels)",
      power_uw: 22000,
      per: "whole part (4 channels)",
      source_name: "ADS1299 datasheet (Texas Instruments)",
      source_url: "https://www.ti.com/document-viewer/ADS1299/datasheet/specifications",
      quote: "ADS1299-4 normal mode 22 / 24 mW typ/max",
      kind: "datasheet",
    },
    // --- Low-channel biopotential front ends (Texas Instruments datasheets,
    // read as text from the maker's PDF). role "eeg-budget": the datasheet
    // names EEG and gives power with conditions, so the EEG budget may use it.
    // role "ecg-grade-scale": the datasheet names ECG only; shown for scale,
    // never used in an EEG budget. role "headline-only": names EEG but the
    // power is a feature-list figure without stated conditions; not used.
    {
      id: "ads1194",
      name: "Biopotential front end ADS1194 (4 channels, 16-bit)",
      power_uw: 3000,
      per: "whole part (4 channels), analog supply 3 V",
      channels: 4,
      role: "eeg-budget",
      eeg_named: true,
      channel_quiescent_uw: 350,
      noise_uvpp: 12.2,
      noise_note: "12.2 uVpp (gain 6, 10 s of data; feature list: 12 uVpp, 150 Hz bandwidth, G = 6)",
      source_name: "ADS1194/ADS1196/ADS1198 datasheet SBAS471C (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1198.pdf",
      quote:
        "Quiescent power dissipation, ADS1194 Normal mode 3 / 3.3 mW typ/max (analog supply 3 V, " +
        "RLD, WCT and pace amplifiers turned off; DVDD 1.8 V, 500 SPS, gain 6). " +
        "Quiescent channel power PGA + ADC 350 uW. Channel register: 'PD: 1 = Channel power-down'",
      eeg_quote:
        "make them well-suited for scalable electrocardiogram (ECG), electroencephalography (EEG), " +
        "and electromyography (EMG) applications",
      kind: "datasheet",
    },
    {
      id: "ads1196",
      name: "Biopotential front end ADS1196 (6 channels, 16-bit)",
      power_uw: 3600,
      per: "whole part (6 channels), analog supply 3 V",
      channels: 6,
      role: "eeg-budget",
      eeg_named: true,
      channel_quiescent_uw: 350,
      noise_uvpp: 12.2,
      noise_note: "12.2 uVpp (gain 6, 10 s of data), family figure",
      source_name: "ADS1194/ADS1196/ADS1198 datasheet SBAS471C (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1198.pdf",
      quote:
        "Quiescent power dissipation, ADS1196 Normal mode 3.6 / 4 mW typ/max (analog supply 3 V, " +
        "RLD, WCT and pace amplifiers turned off; DVDD 1.8 V, 500 SPS, gain 6). " +
        "Quiescent channel power PGA + ADC 350 uW",
      eeg_quote:
        "make them well-suited for scalable electrocardiogram (ECG), electroencephalography (EEG), " +
        "and electromyography (EMG) applications",
      kind: "datasheet",
    },
    {
      id: "ads1198",
      name: "Biopotential front end ADS1198 (8 channels, 16-bit)",
      power_uw: 4300,
      per: "whole part (8 channels), analog supply 3 V",
      channels: 8,
      role: "eeg-budget",
      eeg_named: true,
      channel_quiescent_uw: 350,
      noise_uvpp: 12.2,
      noise_note: "12.2 uVpp (gain 6, 10 s of data), family figure",
      source_name: "ADS1194/ADS1196/ADS1198 datasheet SBAS471C (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1198.pdf",
      quote:
        "Quiescent power dissipation, ADS1198 Normal mode 4.3 / 4.8 mW typ/max (analog supply 3 V, " +
        "RLD, WCT and pace amplifiers turned off; DVDD 1.8 V, 500 SPS, gain 6). " +
        "Quiescent channel power PGA + ADC 350 uW. Feature list: Low Power 0.55 mW/channel",
      eeg_quote:
        "make them well-suited for scalable electrocardiogram (ECG), electroencephalography (EEG), " +
        "and electromyography (EMG) applications",
      kind: "datasheet",
    },
    {
      id: "ads1294",
      name: "Biopotential front end ADS1294 (4 channels, 24-bit), high-resolution mode",
      power_uw: 5400,
      per: "whole part (4 channels), analog supply 3 V",
      channels: 4,
      role: "eeg-budget",
      eeg_named: true,
      noise_uvpp: 5,
      noise_note: "5 uVpp (gain 6, 10 s of data; feature list: 4 uVpp, 150 Hz bandwidth, G = 6)",
      source_name: "ADS1294/6/8 datasheet SBAS459K (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1294.pdf",
      quote:
        "Power dissipation, ADS1294, ADS1294R, HR mode 5.4 / 6 mW typ/max (AVDD - AVSS = 3 V; RLD, WCT " +
        "and pace amplifiers turned off; DVDD 1.8 V, 500 SPS, HR mode, gain 6). Feature list: Low Power 0.75 mW/channel",
      eeg_quote:
        "Applications: Medical Instrumentation (ECG, EMG, and EEG); incorporate all of the features that " +
        "are commonly required in medical electrocardiogram (ECG) and electroencephalogram (EEG) applications",
      kind: "datasheet",
    },
    {
      id: "ads1298",
      name: "Biopotential front end ADS1298 (8 channels, 24-bit), high-resolution mode",
      power_uw: 8800,
      per: "whole part (8 channels), analog supply 3 V",
      channels: 8,
      role: "eeg-budget",
      eeg_named: true,
      noise_uvpp: 5,
      noise_note: "5 uVpp (gain 6, 10 s of data), family figure",
      source_name: "ADS1294/6/8 datasheet SBAS459K (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1294.pdf",
      quote:
        "Power dissipation, ADS1298, ADS1298R, HR mode 8.8 / 9.5 mW typ/max (AVDD - AVSS = 3 V; RLD, WCT " +
        "and pace amplifiers turned off; DVDD 1.8 V, 500 SPS, HR mode, gain 6)",
      eeg_quote:
        "Applications: Medical Instrumentation (ECG, EMG, and EEG); incorporate all of the features that " +
        "are commonly required in medical electrocardiogram (ECG) and electroencephalogram (EEG) applications",
      kind: "datasheet",
    },
    {
      id: "afe1594",
      name: "Biopotential front end AFE1594 (4 channels, 24-bit), headline figure only",
      power_uw: 1680,
      per: "whole part (4 channels), 4 x 0.42 mW; conditions not stated",
      channels: 4,
      role: "headline-only",
      eeg_named: true,
      noise_uvpp: 4,
      noise_note: "4 uVpp (150 Hz bandwidth)",
      source_name: "AFE159x datasheet SBASB28A (Texas Instruments), abridged production version",
      source_url: "https://www.ti.com/lit/ds/symlink/afe1594.pdf",
      quote:
        "Four high resolution channels at low power of 0.42mW/channel (feature list; the version read has " +
        "no electrical table, so supply and mode are not stated; 4 x 0.42 mW = 1.68 mW is our product). " +
        "Input-referred noise: 4 uVpp in 150Hz BW",
      eeg_quote:
        "Medical instrumentation (ECG, EMG, and EEG); electrocardiogram (ECG) and electroencephalogram (EEG) applications",
      kind: "datasheet",
    },
    {
      id: "ads1191",
      name: "ECG front end ADS1191 (1 channel, 16-bit), ECG-grade, shown for scale",
      power_uw: 450,
      per: "whole part (1 channel), analog supply 3 V",
      channels: 1,
      role: "ecg-grade-scale",
      eeg_named: false,
      noise_uvpp: 24,
      noise_note: "24 uVpp (150 Hz bandwidth, G = 6)",
      source_name: "ADS1191/ADS1192 datasheet SBAS566A (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1191.pdf",
      quote:
        "Quiescent power dissipation, ADS1191 Normal mode 450 / 495 uW typ/max (analog supply 3 V, RLD turned off; " +
        "DVDD 1.8 V, 500 SPS, gain 6). Applications: Medical Instrumentation (ECG); the sheet does not name EEG as an application",
      kind: "datasheet",
    },
    {
      id: "ads1192",
      name: "ECG front end ADS1192 (2 channels, 16-bit), ECG-grade, shown for scale",
      power_uw: 670,
      per: "whole part (2 channels), analog supply 3 V",
      channels: 2,
      role: "ecg-grade-scale",
      eeg_named: false,
      noise_uvpp: 24,
      noise_note: "24 uVpp (150 Hz bandwidth, G = 6)",
      source_name: "ADS1191/ADS1192 datasheet SBAS566A (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1191.pdf",
      quote:
        "Quiescent power dissipation, ADS1192 Normal mode 670 / 740 uW typ/max (analog supply 3 V, RLD turned off; " +
        "DVDD 1.8 V, 500 SPS, gain 6). Applications: Medical Instrumentation (ECG); the sheet does not name EEG as an application",
      kind: "datasheet",
    },
    {
      id: "ads1291",
      name: "ECG front end ADS1291 (1 channel, 24-bit), ECG-grade, shown for scale",
      power_uw: 450,
      per: "whole part (1 channel), analog supply 3 V",
      channels: 1,
      role: "ecg-grade-scale",
      eeg_named: false,
      noise_uvpp: 8,
      noise_note: "8 uVpp (150 Hz bandwidth, G = 6)",
      source_name: "ADS1291/ADS1292/ADS1292R datasheet SBAS502C (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1291.pdf",
      quote:
        "Quiescent power dissipation, ADS1291 Normal mode 450 / 495 uW typ/max (analog supply 3 V, RLD turned off; " +
        "DVDD 1.8 V, 500 SPS, gain 6). Description: portable, low-power medical electrocardiogram (ECG), sports, and " +
        "fitness applications; the sheet does not name EEG as an application",
      kind: "datasheet",
    },
    {
      id: "ads1292",
      name: "ECG front end ADS1292 (2 channels, 24-bit), ECG-grade, shown for scale",
      power_uw: 670,
      per: "whole part (2 channels), analog supply 3 V",
      channels: 2,
      role: "ecg-grade-scale",
      eeg_named: false,
      noise_uvpp: 8,
      noise_note: "8 uVpp (150 Hz bandwidth, G = 6)",
      source_name: "ADS1291/ADS1292/ADS1292R datasheet SBAS502C (Texas Instruments)",
      source_url: "https://www.ti.com/lit/ds/symlink/ads1291.pdf",
      quote:
        "Quiescent power dissipation, ADS1292 and ADS1292R Normal mode 670 / 740 uW typ/max (analog supply 3 V, RLD turned off; " +
        "DVDD 1.8 V, 500 SPS, gain 6). Description: portable, low-power medical electrocardiogram (ECG), sports, and " +
        "fitness applications; the sheet does not name EEG as an application",
      kind: "datasheet",
    },
    {
      id: "ble-nrf52832",
      name: "Bluetooth LE radio nRF52832, connected at 1 s",
      power_uw: 28.4,
      per: "whole part",
      source_name: "Nordic DevZone current-measurement guide",
      source_url: "https://devzone.nordicsemi.com/tutorials/29/",
      quote:
        "Connection at 1000 ms averages 9.47 uA (via search; Engineering B silicon; " +
        "supply voltage not stated, 3 V assumed: 9.47 uA x 3 V = 28.4 uW)",
      kind: "assumed",
    },
    {
      id: "ble-cc2340r5",
      name: "Bluetooth LE radio CC2340R5, connected at 1 s, 1M PHY, 0 dBm",
      power_uw: 21,
      per: "whole part",
      source_name: "Bluetooth LE Software Product Brief CC2340, SWRA793A (Texas Instruments)",
      source_url: "https://www.ti.com/lit/an/swra793a/swra793a.pdf",
      quote:
        "Table 6-1 Connection - PHYs: 1M, 0 dbm, connection interval 1 sec, current consumption 7 uA. " +
        "The brief does not state the supply voltage; 3.0 V is the CC2340R5 datasheet's test supply " +
        "(VDDS = 3.0V, DCDC enabled), assumed here: 7 uA x 3.0 V = 21 uW",
      kind: "assumed",
    },
    {
      id: "radar-bgt60tr13c-active",
      name: "60 GHz radar BGT60TR13C, fully active",
      power_uw: 362000,
      per: "whole part",
      source_name: "BGT60TR13C datasheet (Infineon), Table 6",
      source_url:
        "https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60tr13c-datasheet-en.pdf",
      quote: "Idd Active 3Rx+1Tx 201 mA typ at 1.8 V (about 362 mW)",
      kind: "datasheet",
    },
    {
      id: "radar-bgt60tr13c-duty",
      name: "60 GHz radar BGT60TR13C, 1% duty cycle",
      power_uw: 3800,
      per: "whole part",
      source_name: "BGT60TR13C datasheet (Infineon), Table 6, with an assumed duty cycle",
      source_url:
        "https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60tr13c-datasheet-en.pdf",
      quote:
        "Assumed 1% active (201 mA) and deep sleep (0.12 mA) otherwise, init phase " +
        "ignored: 2.13 mA x 1.8 V = 3.8 mW. No maker figure for vital-sign duty cycling.",
      kind: "assumed",
    },
    {
      id: "thermal-amg8833",
      name: "Thermal infrared array AMG8833 Grid-EYE",
      power_uw: 14900,
      per: "whole part",
      source_name: "AMG8833 spec sheet (Panasonic)",
      source_url: "https://industrial.panasonic.com/cdbs/www-data/pdf/ADI8000/ADI8000C69.pdf",
      quote: "Typ. 4.5 mA (normal mode); 3.3 V supply from a distributor summary (about 14.9 mW)",
      kind: "assumed",
    },
    {
      id: "ppg-max86140",
      name: "Optical front end MAX86140, low-power mode, LEDs excluded",
      power_uw: 29,
      per: "whole part",
      source_name: "MAX86140 datasheet (mirror copy)",
      source_url: "https://datasheet.chipsmall.com/MAX86140ENP/557693.pdf",
      quote: "Low-power mode 16 uA at 50 sps; 1.8 V supply from a search summary; LED power not included",
      kind: "assumed",
    },
    {
      id: "mcu-apollo3",
      name: "Microcontroller Apollo3 Blue (Cortex-M4F), active",
      power_uw: 19.8,
      per: "per MHz",
      source_name: "Apollo3 Blue SoC datasheet (Ambiq)",
      source_url: "https://cdn.sparkfun.com/assets/c/8/3/d/2/Apollo3-Blue-SoC-Datasheet.pdf",
      quote: "6 uA/MHz executing from FLASH or RAM at 3.3 V (19.8 uW per MHz)",
      kind: "datasheet",
    },
    {
      id: "mcu-nrf52832",
      name: "Microcontroller nRF52832 (Cortex-M4F), active",
      power_uw: 174,
      per: "per MHz",
      source_name: "nRF52832 product specification, CPU page (Nordic)",
      source_url: "https://docs.nordicsemi.com/r/bundle/ps_nrf52832/page/cpu.html",
      quote: "58 uA/MHz, running from flash, cache enabled, DCDC 3V (quoted via search)",
      kind: "assumed",
    },
    {
      id: "chip",
      name: "ChipIn classifier chip (fixed logic)",
      power_uw: 0.05,
      per: "whole chip, 2,607 gates at one decision per second",
      source_name: "ChipIn lab layout report (sky130, one run)",
      source_url: null,
      quote:
        "Power at one decision per second is under 0.05 uW for each classifier " +
        "(0.026858 uW at 1,279 gates to 0.049067 uW at 2,607 gates); untrained placeholder weights",
      kind: "estimate",
    },
  ];

  function part(id) {
    for (var i = 0; i < PARTS.length; i++) if (PARTS[i].id === id) return PARTS[i];
    throw new Error("unknown part " + id);
  }

  /*
   * Chip power model (estimate). Power is taken as proportional to the gate
   * count and to the decision rate: P = UW_PER_GATE x gates x decisions/s.
   * UW_PER_GATE is the mean of the three lab designs' power per gate at one
   * decision per second (0.04986/2367, 0.049067/2607, 0.026858/1279), which
   * is about 2.03e-5 uW per gate. It reproduces 0.026 uW at 1,279 gates and
   * 0.053 uW at 2,607 gates. One run, one process (sky130), layout-based,
   * untrained weights; linear scaling in gates and rate is our assumption.
   */
  var CHIP_POWER_MODEL = {
    uw_per_gate_per_decision_per_s: (0.04986 / 2367 + 0.049067 / 2607 + 0.026858 / 1279) / 3,
    points: [
      { gates: 1279, decisions_per_s: 1, power_uw: 0.026858 },
      { gates: 2367, decisions_per_s: 1, power_uw: 0.04986 },
      { gates: 2607, decisions_per_s: 1, power_uw: 0.049067 },
    ],
    kind: "estimate",
    assumption:
      "Estimate from one layout run in one process (sky130) with untrained " +
      "placeholder weights, at one decision per second (0.027 to 0.050 uW for " +
      "1,279 to 2,607 gates). Scaled in proportion to gates and decision rate; " +
      "not measured on silicon.",
  };

  function chipPowerUw(gates, decisionsPerSecond) {
    var dps = decisionsPerSecond === undefined ? 1 : decisionsPerSecond;
    return CHIP_POWER_MODEL.uw_per_gate_per_decision_per_s * Math.max(0, gates) * Math.max(0, dps);
  }

  function lineFromPart(p, count, label) {
    return {
      name: label || p.name,
      power_uw: p.power_uw * count,
      kind: p.kind,
      source_name: p.source_name,
      source_url: p.source_url,
    };
  }

  /*
   * EEG front-end rule. Candidates are the parts with role "eeg-budget": the
   * maker's datasheet names EEG and gives power with conditions. Parts whose
   * datasheet names ECG only (role "ecg-grade-scale") and headline-only
   * figures are never used. For n channels the model takes the cheapest
   * combination of candidate parts that covers n channels, by total power,
   * and per part it enables only the channels needed.
   *   policy "lowest-power" (default): all candidates.
   *   policy "low-noise": only the candidates with the lowest quoted
   *     input-referred noise figure (the ADS1299 family). The noise figures
   *     are quoted at different bandwidths and gains, so they are not
   *     directly comparable; each part carries its own noise_note.
   * The datasheets give device totals. Where a part also gives a quiescent
   * power per channel (channel_quiescent_uw) and a per-channel power-down
   * bit, a part with unused channels is costed as total minus that figure per
   * unused channel: this is our estimate, not a datasheet figure.
   */
  var FRONT_END_POLICIES = {
    "lowest-power":
      "Cheapest combination, by datasheet power, of parts whose datasheet names EEG and states the power conditions.",
    "low-noise":
      "Only the EEG-named parts with the lowest quoted input-referred noise (the ADS1299 family), cheapest combination by power.",
  };

  function eegCandidates(policy) {
    var c = PARTS.filter(function (p) {
      return p.role === "eeg-budget" && p.eeg_named === true;
    });
    if (policy === "low-noise") {
      var best = Infinity;
      c.forEach(function (p) {
        best = Math.min(best, p.noise_uvpp);
      });
      c = c.filter(function (p) {
        return p.noise_uvpp === best;
      });
    }
    c.sort(function (a, b) {
      return a.channels - b.channels || a.power_uw - b.power_uw;
    });
    return c;
  }

  function enabledPower(p, m) {
    if (m < p.channels && p.channel_quiescent_uw) {
      return { power_uw: p.power_uw - (p.channels - m) * p.channel_quiescent_uw, estimate: true };
    }
    return { power_uw: p.power_uw, estimate: false };
  }

  /** Cheapest cover of n EEG channels: [{ part, enabled, power_uw, estimate }]. */
  function eegPlan(n, policy) {
    n = Math.max(1, Math.round(n));
    var cands = eegCandidates(policy || "lowest-power");
    var best = [{ p: 0, picks: [] }];
    for (var c = 1; c <= n; c++) {
      var cur = null;
      for (var i = 0; i < cands.length; i++) {
        var m = Math.min(c, cands[i].channels);
        var ep = enabledPower(cands[i], m);
        var prev = best[c - m];
        var cost = prev.p + ep.power_uw;
        if (cur === null || cost < cur.p - 1e-9) {
          cur = {
            p: cost,
            picks: prev.picks.concat([{ part: cands[i], enabled: m, power_uw: ep.power_uw, estimate: ep.estimate }]),
          };
        }
      }
      best.push(cur);
    }
    return best[n].picks;
  }

  function eegFrontEnd(n, policy) {
    var groups = [];
    eegPlan(n, policy).forEach(function (pk) {
      for (var i = 0; i < groups.length; i++) {
        if (groups[i].part === pk.part && groups[i].enabled === pk.enabled) {
          groups[i].count++;
          return;
        }
      }
      groups.push({ part: pk.part, enabled: pk.enabled, power_uw: pk.power_uw, estimate: pk.estimate, count: 1 });
    });
    return groups.map(function (g) {
      var name = g.part.name;
      if (g.enabled < g.part.channels) {
        name = name + ", " + g.enabled + " of " + g.part.channels + " channels enabled, the rest powered down";
      }
      if (g.count > 1) name = g.count + " x " + name;
      return {
        name: name,
        power_uw: g.power_uw * g.count,
        kind: g.estimate ? "estimate" : g.part.kind,
        source_name: g.part.source_name,
        source_url: g.part.source_url,
      };
    });
  }

  var DEVICE_KINDS = {
    "ecg-patch": { name: "ECG patch", unit: "leads", budgets: [1, 2, 3, 4, 6, 8] },
    "eeg-monitor": { name: "EEG monitor", unit: "channels", budgets: [1, 2, 4, 8, 16] },
    "incubator-radar-thermal": { name: "Incubator monitor", unit: "sensors", budgets: [1, 2] },
  };

  /*
   * Total device power, chip as one line.
   *   ecg-patch: one MAX30003 per lead.
   *   eeg-monitor: the cheapest set of EEG-named datasheet parts covering the
   *     channels (see the EEG front-end rule above; option frontEnd is
   *     "lowest-power" (default) or "low-noise").
   *   incubator-radar-thermal: sensors 1 = radar only (assumed 1% duty),
   *     sensors 2 = radar plus thermal infrared array.
   * Regulator losses, self-discharge and the MCU are not included.
   */
  function deviceBudget(o) { // options also: frontEnd, radioPart (a PARTS id)
    o = o || {};
    var kind = o.kind || "ecg-patch";
    var lines = [];
    if (kind === "ecg-patch") {
      var leads = Math.max(1, Math.round(o.channels || 1));
      lines.push(lineFromPart(part("max30003"), leads, leads > 1 ? leads + " x " + part("max30003").name : null));
    } else if (kind === "eeg-monitor") {
      lines = lines.concat(eegFrontEnd(o.channels || 8, o.frontEnd));
    } else if (kind === "incubator-radar-thermal") {
      var sensors = Math.max(1, Math.round(o.sensors || o.channels || 2));
      lines.push(lineFromPart(part("radar-bgt60tr13c-duty"), 1));
      if (sensors >= 2) lines.push(lineFromPart(part("thermal-amg8833"), 1));
    } else {
      throw new Error("unknown device kind " + kind);
    }
    if (o.radio !== false) lines.push(lineFromPart(part(o.radioPart || "ble-nrf52832"), 1));
    var chip = part("chip");
    lines.push({
      name: chip.name,
      power_uw: chipPowerUw(o.gates === undefined ? 2500 : o.gates, o.decisionsPerSecond),
      kind: "estimate",
      source_name: chip.source_name,
      source_url: chip.source_url,
    });
    var total = 0;
    lines.forEach(function (l) {
      total += l.power_uw;
    });
    lines.forEach(function (l) {
      l.share = total > 0 ? l.power_uw / total : 0;
    });
    return { lines: lines, total_uw: total, chip_share: lines[lines.length - 1].share };
  }

  // ------------------------------------------------------------------ C.
  // Battery classes

  var CELLS = [
    {
      id: "cr2032",
      name: "CR2032 coin cell (Panasonic)",
      type: "primary",
      capacity_mah: 225,
      voltage_v: 3,
      continuous_ma: 0.2,
      size: "20.0 mm x 3.2 mm, about 2.8 g",
      source_name: "Panasonic CR2032 datasheet",
      source_url: "https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR2032_Datasheet_EN.pdf",
      quote: "Nominal voltage 3V; Nominal capacity 225mAh; Continuous drain 0.2mA",
      kind: "datasheet",
    },
    {
      id: "cr1632",
      name: "CR1632 coin cell (Panasonic)",
      type: "primary",
      capacity_mah: 140,
      voltage_v: 3,
      continuous_ma: 0.1,
      size: "16.0 mm x 3.2 mm, about 1.9 g",
      source_name: "Panasonic CR1632 datasheet",
      source_url: "https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR1632_Datasheet_EN.pdf",
      quote: "Nominal voltage 3V; Nominal capacity 140mAh; Continuous drain 0.1mA",
      kind: "datasheet",
    },
    {
      id: "cr1220",
      name: "CR1220 coin cell (Panasonic)",
      type: "primary",
      capacity_mah: 35,
      voltage_v: 3,
      continuous_ma: 0.1,
      size: "12.5 mm x 2.0 mm, about 0.9 g",
      source_name: "Panasonic CR1220 datasheet",
      source_url: "https://energy.panasonic.com/dam/master/pdf/en/datasheet/lithium/CR1220_Datasheet_EN.pdf",
      quote: "Nominal voltage 3V; Nominal capacity 35mAh; Continuous drain 0.1mA",
      kind: "datasheet",
    },
    {
      id: "cr2032-energizer",
      name: "CR2032 coin cell (Energizer)",
      type: "primary",
      capacity_mah: 235,
      voltage_v: 3,
      continuous_ma: 0.19,
      size: "20 mm coin",
      source_name: "Energizer CR2032 datasheet (search-tool quote; direct fetch failed)",
      source_url: "https://data.energizer.com/pdfs/cr2032.pdf",
      quote: "Typical capacity 235 mAh to 2.0 V; continuous 0.19 mA at 2.9 V",
      kind: "assumed",
    },
    {
      id: "icp621333",
      name: "ICP621333HPMT rechargeable lithium polymer pouch cell (Renata)",
      type: "rechargeable",
      capacity_mah: 270,
      capacity_min_mah: 260,
      voltage_v: 3.8,
      continuous_ma: 270,
      size: "35 mm x 13 mm x 6.8 mm, about 5.6 g, with safety circuit",
      source_name: "Renata ICP621333HPMT datasheet Rev V01 11/2020 (copy hosted by Conrad)",
      source_url:
        "https://asset.conrad.com/media10/add/160267/c1/-/gl/003015330DS00/tehnicni-podatki-3015330-renata-icp621333hpmt-specialni-akumulatorji-prismaticno-kabel-lipo-37-v-270-mah.pdf",
      quote:
        "Nominal Voltage 3.8 V; Typical Capacity 270 mAh; Minimum Capacity 260 mAh (0.2C cut off 3.0 V at 20C); " +
        "Max discharge Current 1.0 C - 270 mA (for continues discharge); Cycle Life > 80% of minimum capacity after 500 cycles",
      kind: "datasheet",
    },
    {
      id: "lir2032",
      name: "LIR2032 rechargeable coin cell",
      type: "rechargeable",
      capacity_mah: 35,
      capacity_range_mah: [35, 45],
      voltage_v: 3.6,
      continuous_ma: null,
      size: "20 mm coin, same case as CR2032",
      source_name: "Vendor pages (no maker datasheet verified)",
      source_url: "https://www.powerstream.com/licoin.htm",
      quote:
        "3.6 V nominal, 35 to 45 mAh depending on maker; charge 4.2 V CC/CV, 3 mA standard. " +
        "No continuous discharge limit sourced. Lower capacity used.",
      kind: "assumed",
    },
  ];

  function cell(id) {
    for (var i = 0; i < CELLS.length; i++) if (CELLS[i].id === id) return CELLS[i];
    throw new Error("unknown cell " + id);
  }

  /*
   * ILLUSTRATIVE minimum useful life: a device whose cell lasts less than
   * this between replacements or charges is treated as needing a larger pack
   * or mains. This is a stand-in for the user's own requirement, not a
   * clinical or regulatory figure.
   */
  var ILLUSTRATIVE_MIN_LIFE_HOURS = 24;

  var REFERENCE_PRIMARY = "cr2032";
  var REFERENCE_RECHARGEABLE = "icp621333";

  function cellLifeHours(c, totalUw) {
    var mwh = c.capacity_mah * c.voltage_v;
    return totalUw > 0 ? mwh / (totalUw / 1000) : Infinity;
  }

  function cellCurrentMa(c, totalUw) {
    return totalUw / 1000 / c.voltage_v;
  }

  /*
   * Two explicit checks, applied first to the reference coin cell (CR2032)
   * and then to the reference rechargeable (the Renata ICP621333HPMT pouch
   * cell, a few hundred mAh; the LIR2032 coin cell stays in CELLS, assumed,
   * unused here):
   *   1. average current (total power / cell voltage) within the cell's
   *      continuous-current rating (skipped where no rating is sourced);
   *   2. life (energy / total power) at least ILLUSTRATIVE_MIN_LIFE_HOURS.
   * Life ignores self-discharge, regulator losses and capacity loss at load.
   */
  function batteryClass(totalUw) {
    var p = cell(REFERENCE_PRIMARY);
    var r = cell(REFERENCE_RECHARGEABLE);
    var pI = cellCurrentMa(p, totalUw);
    var pLife = cellLifeHours(p, totalUw);
    var minDays = ILLUSTRATIVE_MIN_LIFE_HOURS / 24;
    var lim = "an illustrative minimum of " + ILLUSTRATIVE_MIN_LIFE_HOURS + " hours";
    if (pI <= p.continuous_ma && pLife >= ILLUSTRATIVE_MIN_LIFE_HOURS) {
      return {
        class: "primary coin cell",
        cell: p,
        life_days: pLife / 24,
        current_ma: pI,
        reason:
          "Average draw " + pI.toFixed(3) + " mA is within the " + p.name + "'s " +
          p.continuous_ma + " mA continuous rating, and it lasts about " +
          Math.round(pLife / 24) + " days.",
      };
    }
    var why =
      pI > p.continuous_ma
        ? "Average draw " + pI.toFixed(2) + " mA exceeds the " + p.name + "'s " +
          p.continuous_ma + " mA continuous rating"
        : "A " + p.name + " lasts only " + pLife.toFixed(1) + " hours, under " + lim;
    var rLife = cellLifeHours(r, totalUw);
    var rI = cellCurrentMa(r, totalUw);
    var rCurrentOk = r.continuous_ma === null || rI <= r.continuous_ma;
    if (rCurrentOk && rLife >= ILLUSTRATIVE_MIN_LIFE_HOURS) {
      return {
        class: "rechargeable lithium",
        cell: r,
        life_days: rLife / 24,
        current_ma: rI,
        reason:
          why + "; a " + r.name + " lasts about " + (rLife / 24).toFixed(1) +
          " days per charge" +
          (r.continuous_ma === null
            ? " (no continuous-current rating sourced for it)."
            : ", at " + rI.toFixed(2) + " mA, within its " + r.continuous_ma + " mA continuous rating."),
      };
    }
    return {
      class: "larger pack or mains",
      cell: null,
      life_days: rLife / 24,
      current_ma: rI,
      reason:
        why + "; a " + r.name + " would last only " + rLife.toFixed(1) +
        " hours per charge, under " + lim + " (" + minDays + " day).",
    };
  }

  /** For each channel or sensor budget of a device kind: total power, class, life. */
  function classBoundaries(kind, opts) {
    opts = opts || {};
    var k = DEVICE_KINDS[kind];
    if (!k) throw new Error("unknown device kind " + kind);
    var budgets = opts.budgets || k.budgets;
    return budgets.map(function (n) {
      var b = deviceBudget({
        kind: kind,
        channels: n,
        sensors: n,
        radio: opts.radio !== false,
        gates: opts.gates === undefined ? 2500 : opts.gates,
        decisionsPerSecond: opts.decisionsPerSecond,
        frontEnd: opts.frontEnd,
        radioPart: opts.radioPart,
      });
      var c = batteryClass(b.total_uw);
      return {
        budget: n,
        unit: k.unit,
        total_uw: b.total_uw,
        chip_share: b.chip_share,
        class: c.class,
        cell: c.cell ? c.cell.name : null,
        life_days: c.life_days,
        current_ma: c.current_ma,
        reason: c.reason,
      };
    });
  }

  function lifeText(days) {
    return days >= 2 ? Math.round(days) + " days" : (days * 24).toFixed(1) + " hours";
  }

  function mw(uw) {
    return (uw / 1000).toFixed(uw < 1000 ? 3 : 2) + " mW";
  }

  /*
   * channelStory(kind, opts): what the number of channels (leads, sensors)
   * does to the battery, computed from classBoundaries. Returns
   * { text, estimate: true, tips: [{ budget, unit, from, to, text }], rows }.
   * A tip is a budget at which the class changes from the previous budget.
   * With no tip the sentence says the count changes hours per charge, not
   * the class. For EEG it adds, from the same model, the lowest-noise front
   * end and the ECG-grade single-channel part shown for scale.
   */
  function channelStory(kind, opts) {
    opts = opts || {};
    var k = DEVICE_KINDS[kind];
    if (!k) throw new Error("unknown device kind " + kind);
    var rows = classBoundaries(kind, opts);
    var first = rows[0];
    var last = rows[rows.length - 1];
    var tips = [];
    for (var i = 1; i < rows.length; i++) {
      if (rows[i].class !== rows[i - 1].class) {
        tips.push({
          budget: rows[i].budget,
          unit: k.unit,
          from: rows[i - 1].class,
          to: rows[i].class,
          text:
            "At " + rows[i].budget + " " + k.unit + " (" + mw(rows[i].total_uw) + ") the battery tips from " +
            rows[i - 1].class + " to " + rows[i].class + ", against " + mw(rows[i - 1].total_uw) +
            " at " + rows[i - 1].budget + ".",
        });
      }
    }
    var parts = [];
    var who = k.name;
    if (tips.length === 0) {
      parts.push(
        "For the " + who + ", going from " + first.budget + " to " + last.budget + " " + k.unit +
          " changes hours per charge and not the class: " + mw(first.total_uw) + " to " + mw(last.total_uw) +
          ", " + lifeText(first.life_days) + " to " + lifeText(last.life_days) + " per " +
          (first.class === "primary coin cell" ? "cell" : "charge") + ", " + first.class + " throughout."
      );
    } else {
      parts.push(
        "For the " + who + ", " + tips.map(function (t) { return t.text.charAt(0).toLowerCase() + t.text.slice(1); }).join(" ") +
          " From " + first.budget + " to " + last.budget + " " + k.unit + " battery life goes from " +
          lifeText(first.life_days) + " to " + lifeText(last.life_days) + "."
      );
    }
    if (kind === "eeg-monitor") {
      var smallest = eegCandidates(opts.frontEnd)[0];
      parts.push(
        "No datasheet part that names EEG has fewer than " + smallest.channels + " channels (smallest: " +
          smallest.name.split(" (")[0] + "), so fewer channels save only the unused channels switched off, " +
          "an estimate from the datasheet's per-channel figure."
      );
      var lowNoiseRows = classBoundaries(kind, {
        budgets: opts.budgets,
        radio: opts.radio,
        gates: opts.gates,
        decisionsPerSecond: opts.decisionsPerSecond,
        radioPart: opts.radioPart,
        frontEnd: "low-noise",
      });
      var ln = lowNoiseRows[0];
      var lnLast = lowNoiseRows[lowNoiseRows.length - 1];
      var lnClasses = [];
      lowNoiseRows.forEach(function (r) {
        if (lnClasses.indexOf(r.class) < 0) lnClasses.push(r.class);
      });
      parts.push(
        "With the lowest-noise front end read (ADS1299 family) it is " + mw(ln.total_uw) + " at " + ln.budget +
          " to " + mw(lnLast.total_uw) + " at " + lnLast.budget + " " + k.unit + ": " + lnClasses.join(" or ") + ". Switching front end changes power by " +
          (ln.total_uw / first.total_uw).toFixed(1) + " times at the smallest count, and the channel count by " + (last.total_uw / first.total_uw).toFixed(1) + " times from " +
          first.budget + " to " + last.budget + "."
      );
      var scale = PARTS.filter(function (p) {
        return p.role === "ecg-grade-scale" && p.channels === 1;
      }).sort(function (a, b) {
        return a.power_uw - b.power_uw;
      })[0];
      if (scale) {
        var b = deviceBudget({
          kind: kind,
          channels: 1,
          radio: opts.radio,
          gates: opts.gates,
          decisionsPerSecond: opts.decisionsPerSecond,
          radioPart: opts.radioPart,
        });
        var base = b.total_uw - b.lines[0].power_uw;
        var cls = batteryClass(base + scale.power_uw);
        parts.push(
          "For scale only: a 1-channel ECG-grade part (" + scale.name.split(" (")[0] + ", " + mw(scale.power_uw) +
            ", noise " + scale.noise_uvpp + " uVpp) would give " + cls.class + " at 1 channel, but its datasheet " +
            "names ECG and not EEG, so no EEG budget uses it."
        );
      }
    }
    return { text: parts.join(" "), estimate: true, tips: tips, rows: rows };
  }

  var GENERAL = "general engineering knowledge";

  var CONSEQUENCES = {
    "primary coin cell": [
      { text: "Single use: the cell is not replaced or recharged.", kind: GENERAL },
      { text: "No charging circuit or charging contacts.", kind: GENERAL },
      { text: "No reprocessing between patients if the device is single use.", kind: GENERAL },
      {
        text: "Lithium coin cells still need transport testing (UN 38.3) under the US rule text.",
        kind: "sourced",
        source_name: "49 CFR 173.185(a)(1)",
        source_url: "https://www.law.cornell.edu/cfr/text/49/173.185",
      },
    ],
    "rechargeable lithium": [
      { text: "Charging circuit and charging contacts or a wireless coil.", kind: GENERAL },
      { text: "Thermal limits for parts touching the skin while charging.", kind: GENERAL },
      {
        text: "Cleaning and reprocessing validation if the device is reused between patients.",
        kind: "sourced",
        source_name: "FDA guidance: Reprocessing Medical Devices in Health Care Settings (2015)",
        source_url:
          "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/reprocessing-medical-devices-health-care-settings-validation-methods-and-labeling",
      },
      {
        text: "Safety requirements for secondary lithium cells apply (IEC 62133-2).",
        kind: "sourced",
        source_name: "IEC 62133-2 listing (AFNOR)",
        source_url: "https://www.boutique.afnor.org/en-gb/standard/iec-6213322017//xs129449/252956",
      },
      { text: "Service life and capacity loss over charge cycles.", kind: GENERAL },
      { text: "More regulatory work than a sealed single-use device.", kind: GENERAL },
    ],
    "larger pack or mains": [
      { text: "A larger battery pack or a mains supply; no longer a small patch.", kind: GENERAL },
      { text: "Cables or a docking station near the patient.", kind: GENERAL },
      { text: "More regulatory work for the power supply and its isolation.", kind: GENERAL },
    ],
  };

  // ------------------------------------------------------------------ D.
  // Cost: an editable model. EVERY default below is illustrative; there are
  // no sourced cost figures. Currency: US dollars.

  var COST_DEFAULTS = {
    annual_volume: 100000,
    process_node: "130 nm (illustrative)",
    wafer_cost: 3000,
    wafer_diameter_mm: 200,
    // Logic area per gate, placed, in square micrometres. Illustrative,
    // in the range of a 130 nm standard-cell layout.
    area_per_gate_um2: 10,
    // Pad-limited floor: the input and output pads set a minimum die size,
    // so below this the die does not shrink with fewer gates.
    pad_limited_floor_mm2: 1.0,
    // Optional explicit die area; null means max(floor, gates x area_per_gate).
    die_area_mm2: null,
    yield: 0.9,
    package_cost: 0.15,
    test_cost: 0.05,
    nre_cost: 0,
    battery_cost: {
      "primary coin cell": 0.3,
      "rechargeable lithium": 2.5,
      "larger pack or mains": 12,
    },
    battery_class: "primary coin cell",
    assembly_cost: 1.0,
    illustrative: true,
  };

  function merge(base, over) {
    var out = {};
    var k;
    for (k in base) out[k] = base[k];
    for (k in over || {}) if (over[k] !== undefined) out[k] = over[k];
    out.battery_cost = {};
    for (k in base.battery_cost) out.battery_cost[k] = base.battery_cost[k];
    if (over && over.battery_cost) for (k in over.battery_cost) out.battery_cost[k] = over.battery_cost[k];
    return out;
  }

  function diesPerWafer(diameterMm, areaMm2) {
    var r = diameterMm / 2;
    var n = (Math.PI * r * r) / areaMm2 - (Math.PI * diameterMm) / Math.sqrt(2 * areaMm2);
    return Math.max(1, Math.floor(n));
  }

  /** costModel({ gates, ...any COST_DEFAULTS key }) */
  function costModel(inputs) {
    var i = merge(COST_DEFAULTS, inputs);
    var gates = i.gates === undefined ? 2500 : i.gates;
    var logicArea = (gates * i.area_per_gate_um2) / 1e6;
    var area = i.die_area_mm2 !== null && i.die_area_mm2 !== undefined
      ? i.die_area_mm2
      : Math.max(i.pad_limited_floor_mm2, logicArea);
    var padLimited = logicArea < i.pad_limited_floor_mm2;
    var dpw = diesPerWafer(i.wafer_diameter_mm, area);
    var dieCost = i.wafer_cost / (dpw * i.yield);
    var nrePerUnit = i.annual_volume > 0 ? i.nre_cost / i.annual_volume : 0;
    var battery = i.battery_cost[i.battery_class] || 0;
    var lines = [
      { name: "Die", cost: dieCost, kind: "assumed" },
      { name: "Package", cost: i.package_cost, kind: "assumed" },
      { name: "Test", cost: i.test_cost, kind: "assumed" },
      { name: "Battery (" + i.battery_class + ")", cost: battery, kind: "assumed" },
      { name: "Assembly", cost: i.assembly_cost, kind: "assumed" },
    ];
    if (nrePerUnit > 0) lines.push({ name: "One-off design and masks, per unit", cost: nrePerUnit, kind: "assumed" });
    var unit = 0;
    lines.forEach(function (l) {
      unit += l.cost;
    });
    var notes = [
      "Every input is an illustrative assumption; there are no sourced cost figures.",
      padLimited
        ? "The die is pad-limited: its area is set by the input and output pads (" +
          i.pad_limited_floor_mm2 + " mm2), not by the " + fmtInt(gates) + " gates (" +
          logicArea.toFixed(3) + " mm2 of logic)."
        : "The logic (" + logicArea.toFixed(3) + " mm2) is larger than the pad-limited floor, so area grows with gates.",
      "Process node: " + i.process_node + ".",
    ];
    return {
      die_cost: dieCost,
      unit_cost: unit,
      die_area_mm2: area,
      logic_area_mm2: logicArea,
      pad_limited: padLimited,
      dies_per_wafer: dpw,
      lines: lines,
      notes: notes,
      inputs: i,
    };
  }

  function money(x) {
    return "$" + Math.abs(x).toFixed(2);
  }

  function pct(x) {
    var v = x * 100;
    return (v < 0.01 ? v.toPrecision(2) : v < 1 ? v.toFixed(3) : v.toFixed(1)) + "%";
  }

  /*
   * costDelta(designA, designB, inputs). Designs: { gates, channels,
   * sensors, kind, decisionsPerSecond }. inputs: cost overrides plus an
   * optional kind and radio flag. One plain sentence plus the numbers.
   */
  function costDelta(designA, designB, inputs) {
    inputs = inputs || {};
    function eval1(d) {
      var kind = d.kind || inputs.kind || "ecg-patch";
      var b = deviceBudget({
        kind: kind,
        channels: d.channels,
        sensors: d.sensors || d.channels,
        radio: inputs.radio !== false,
        gates: d.gates,
        decisionsPerSecond: d.decisionsPerSecond,
      });
      var c = batteryClass(b.total_uw);
      var over = merge(COST_DEFAULTS, inputs);
      over.gates = d.gates;
      over.battery_class = c.class;
      return { budget: b, battery: c, cost: costModel(over) };
    }
    var A = eval1(designA);
    var B = eval1(designB);
    var dg = designB.gates - designA.gates;
    var dc = B.cost.unit_cost - A.cost.unit_cost;
    var gatesPart = dg === 0
      ? "keeps the gate count at " + fmtInt(designA.gates)
      : (dg < 0 ? "saves " : "adds ") + fmtInt(Math.abs(dg)) + " gates (" +
        fmtInt(designA.gates) + " to " + fmtInt(designB.gates) + ")";
    var costPart = Math.abs(dc) < 0.005
      ? "unit cost does not change"
      : "unit cost " + (dc < 0 ? "falls" : "rises") + " by " + money(dc);
    var lifeA = A.battery.life_days;
    var lifeB = B.battery.life_days;
    function life(d) {
      return d >= 2 ? Math.round(d) + " days" : (d * 24).toFixed(1) + " hours";
    }
    var lifePart = A.battery.class === B.battery.class
      ? "battery life goes from " + life(lifeA) + " to " + life(lifeB)
      : "the battery moves from " + A.battery.class + " to " + B.battery.class;
    var text =
      "Going from design A to design B " + gatesPart + "; " + costPart +
      " (illustrative); the chip's share of device power goes from " +
      pct(A.budget.chip_share) + " to " + pct(B.budget.chip_share) + " (estimate); and " +
      lifePart + ".";
    return {
      text: text,
      gates_delta: dg,
      unit_cost_delta: dc,
      chip_share: [A.budget.chip_share, B.budget.chip_share],
      life_days: [lifeA, lifeB],
      battery_class: [A.battery.class, B.battery.class],
    };
  }

  // ------------------------------------------------------------------ E.
  // Tooltips naming the assumption behind each estimated field.

  var ESTIMATE_TEXT = {
    power: CHIP_POWER_MODEL.assumption,
    chip_power: CHIP_POWER_MODEL.assumption,
    device_power:
      "Sum of front-end, radio and chip power. Front-end figures from datasheets; " +
      "the radio figure assumes a 3 V supply and a 1 s connection interval; the " +
      "chip is a layout estimate. Regulator losses are ignored.",
    area:
      "Illustrative: logic area is gates times an assumed area per gate, and the " +
      "die is never smaller than an assumed pad-limited floor.",
    node: "Illustrative process node; the lab estimate used one process (sky130).",
    cost:
      "Illustrative: every input (wafer cost, yield, package, test, battery, " +
      "assembly, volume) is an editable assumption, not a quote.",
    battery_life:
      "Cell energy (datasheet capacity times nominal voltage) divided by total " +
      "device power; self-discharge, capacity loss at load and regulator " +
      "losses are ignored.",
    battery_class:
      "Two checks: average current within the cell's continuous rating, and life " +
      "at least an illustrative " + ILLUSTRATIVE_MIN_LIFE_HOURS + " hours.",
  };

  function describeEstimate(field) {
    return ESTIMATE_TEXT[field] || "Estimate: the assumption behind this figure is not stated.";
  }

  // ---------------------------------------------------------------------------
  // The model a run uses: exactly four, by name; default Opus 5.5. agent and id
  // are what POST /api/runs gets as "agent" and "model" on the local backend:
  // the Claude models run on its default claude agent, the Inkling models on
  // its openrouter agent through OpenRouter (backend/README.md, "Providers").
  var RUN_MODELS = [
    { id: "claude-opus-5-5", name: "Opus 5.5", agent: "claude" },
    { id: "claude-sonnet-5-5", name: "Sonnet 5.5", agent: "claude" },
    { id: "thinkingmachines/inkling-2-mini", name: "Inkling 2 Mini", agent: "openrouter" },
    { id: "thinkingmachines/inkling-2-small", name: "Inkling 2 Small", agent: "openrouter" },
  ];
  var DEFAULT_RUN_MODEL = RUN_MODELS[0];

  /** runModel(id): the RUN_MODELS entry for a model id; anything else (an old
   *  stored "auto", an id from before this list) becomes the closest of the four,
   *  else the default. */
  function runModel(id) {
    var s = String(id || "").toLowerCase();
    var exact = RUN_MODELS.filter(function (m) { return m.id === s; })[0];
    if (exact) return exact;
    if (/sonnet/.test(s)) return RUN_MODELS[1];
    if (/inkling-2-mini/.test(s)) return RUN_MODELS[2];
    if (/inkling-2-small/.test(s)) return RUN_MODELS[3];
    return DEFAULT_RUN_MODEL;
  }

  /** usedModelName(agent, model): the name of the model a run really used. A run
   *  that sent no model ran on its agent's default: claude runs Opus 5.5
   *  (agents.claude_cli.model); any other agent's default is not known here. */
  function usedModelName(agent, model) {
    if (model) {
      var m = RUN_MODELS.filter(function (x) { return x.id === String(model).toLowerCase(); })[0];
      return m ? m.name : String(model);
    }
    if (!agent || agent === "claude" || agent === "auto") return DEFAULT_RUN_MODEL.name;
    return agent === "stub" ? "none (scripted stub)" : "the backend's default";
  }

  var api = {
    version: 1,
    RUN_MODELS: RUN_MODELS,
    DEFAULT_RUN_MODEL: DEFAULT_RUN_MODEL,
    runModel: runModel,
    usedModelName: usedModelName,
    wilson: wilson,
    confidenceHeadline: confidenceHeadline,
    cannotTellApart: cannotTellApart,
    CONFIDENCE_THRESHOLDS: CONFIDENCE_THRESHOLDS,
    PARTS: PARTS,
    CHIP_POWER_MODEL: CHIP_POWER_MODEL,
    DEVICE_KINDS: DEVICE_KINDS,
    chipPowerUw: chipPowerUw,
    deviceBudget: deviceBudget,
    CELLS: CELLS,
    ILLUSTRATIVE_MIN_LIFE_HOURS: ILLUSTRATIVE_MIN_LIFE_HOURS,
    batteryClass: batteryClass,
    classBoundaries: classBoundaries,
    channelStory: channelStory,
    FRONT_END_POLICIES: FRONT_END_POLICIES,
    eegPlan: eegPlan,
    CONSEQUENCES: CONSEQUENCES,
    COST_DEFAULTS: COST_DEFAULTS,
    costModel: costModel,
    costDelta: costDelta,
    describeEstimate: describeEstimate,
    ESTIMATE_TEXT: ESTIMATE_TEXT,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.ChipInModels = api;
})(typeof window !== "undefined" ? window : typeof globalThis !== "undefined" ? globalThis : null);
