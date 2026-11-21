Links to the SkyWater PDK, OpenSTA, OpenROAD flow scripts, FINN, hls4ml, Tiny Tapeout and Verilator pages were added from the project names and were not opened in the check.

# Medical-chip evidence check, 21 Nov 2026

This note records one search pass, run on Saturday 21 November 2026 from about 15:30 to
15:45. Three researchers fetched the claims from their sources. A fourth checked 35 of
them by opening each page, and where it disagrees with the other three, its verdict
stands. An item in the not-found list was not found in this pass; it is not shown to be
absent.

## Prior art

- Taalas HC1 hard-wires Llama 3.1 8B: 17K tokens/sec per user, nearly 10X faster than the
  current state of the art, 20X less to build, 10X less power. Source:
  [Taalas](https://taalas.com/the-path-to-ubiquitous-ai/). Caveat: vendor claims, no date
  on the page; "10X faster" is against a stated state of the art, not an independent
  benchmark.
- HC1 is made on TSMC 6nm, 815 mm2, 53 billion transistors, reported 22 Feb 2026. Source:
  [CNX Software](https://www.cnx-software.com/2026/02/22/taalas-hc1-hardwired-llama-3-1-8b-ai-accelerator-delivers-up-to-17000-tokens-s/).
  Caveat: the page says "designed for 2.5kW servers"; the 250 W figure appears only in a
  reader comment and is not carried.
- Differentiable logic gate networks (DLGN): 98.47% MNIST accuracy at 384,000 gates; small
  model 97.69% at 48,000; FINN 98.40%; CIFAR-10 large x4 62.14% at 5.12M; "beyond a
  million images of MNIST per second on a single CPU core". Source:
  [Petersen 2022](https://arxiv.org/abs/2210.08277), PDF table. Caveat: none given beyond
  the table.
- Convolutional DLGN (2024): CIFAR-10 86.29% with 61M gates, "29x smaller" than the state
  of the art. Source: [arXiv 2411.04732](https://arxiv.org/abs/2411.04732). Caveat: from the
  abstract.
- LogicNets: less than 15 ns latency, on high-energy-physics and network intrusion
  detection tasks. Source: [arXiv 2004.03021](https://arxiv.org/abs/2004.03021).
- PolyLUT: three tasks named (jet ID, MNIST, intrusion); the abstract gives no figures.
  Source: [arXiv 2309.02334](https://arxiv.org/abs/2309.02334).
- NeuraLUT: up to 4.3x lower latency for the same accuracy, on jet tagging and MNIST.
  Source: [arXiv 2403.00849](https://arxiv.org/abs/2403.00849).
- FINN: 12.3M images/s at 0.31 us, 95.8% MNIST accuracy, under 25 W; CIFAR/SVHN 21906
  img/s at 283 us. The abstract also gives 80.1% CIFAR-10 and 94.9% SVHN accuracy.
  Source: [arXiv 1612.07119](https://arxiv.org/abs/1612.07119).
- hls4ml: a latency on the scale of 100 ns for a jet classifier. Source:
  [arXiv 1804.06913](https://arxiv.org/abs/1804.06913).
- AlphaEvolve: proposed a Verilog rewrite for a TPU, integrated into an upcoming TPU. No
  numbers. Source:
  [DeepMind blog, May 2025](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/).
- MCUNet: over 70% ImageNet top-1; 3.5x less SRAM and 5.7x less Flash. Source:
  [arXiv 2007.10319](https://arxiv.org/abs/2007.10319). Caveat: the savings are relative to
  quantized MobileNetV2 and ResNet-18.
- Once-for-All: more than 10^19 sub-networks; 80.0% ImageNet accuracy under 600M MACs;
  "same accuracy but 1.5x faster than MobileNetV3" (the comparison also includes
  EfficientNet). Source: [arXiv 1908.09791](https://arxiv.org/abs/1908.09791).
- Tiny Classifiers: <=300 gates; 3-11x FPGA, 8-18x area, 4-8x power, on tabular data.
  Source: [arXiv 2303.00031](https://arxiv.org/abs/2303.00031).
- Mubarik et al., MICRO 2020: bespoke printed EGT decision trees 48.9x lower area and 75.6x
  lower power on average, across seven datasets (six UCI plus HAR), including Arrhythmia
  (ECG). Source: [Mubarik et al. 2020](https://rakeshk.web.engr.illinois.edu/micro20.pdf).
  Caveat: the figures are for printed bespoke decision trees only, not silicon; the
  CNT-TFT comparison is 62.6x area and 27.3x power.

## Medical chips, data and rules

- LGN/LUTN classifier on an ECG task (arXiv 2609.32854): 94.41%; 2.89k-6.17k FLOPs; 8.25 uJ;
  6-LUTN; ZedBoard. The LUTN classifier alone 0.46 nJ; jk index 0.683, four-class task;
  submitted 26 Sep 2026. Source: [arXiv 2609.32854](https://arxiv.org/abs/2609.32854).
- Earlier version 2601.11433 is withdrawn: "withdrawn by Wout Mommen ... major changes,
  leading to different results"; the withdrawal (v2) is dated 29 Sep 2026. Source:
  [arXiv 2601.11433](https://arxiv.org/abs/2601.11433). Caveat: the 16 Jan 2026 date of v1
  was not read; the 94.41% comes from the replacement paper.
- Diff-Logic EEG (arXiv 2607.18149): 80.2% Macro F1 (+6.8% over MLP); 7 W on a Jetson Orin
  Nano single-core CPU. Source: [arXiv 2607.18149](https://arxiv.org/abs/2607.18149).
- Wearable AF patch with hardware-aware NAS on an FPGA (arXiv 2508.13181): 95% accuracy at
  3.8 mW; more than 3 weeks of continuous operation; "surpassing cardiologist-level
  performance". Source: [arXiv 2508.13181](https://arxiv.org/abs/2508.13181). Caveat: 95%
  is the accuracy as stated, not a sensitivity or per-class figure.
- LUT-based 1D-CNN for AF (arXiv 2605.29994): F1 up to 95%; 2,844 LUTs; no DSP or BRAM;
  MIT-BIH; Spartan 7 S15; v1 28 May 2026, v2 29 May 2026. Source:
  [arXiv 2605.29994](https://arxiv.org/abs/2605.29994).
- SparrowSNN (arXiv 2406.06543): a "uW-level-power" hybrid ANN-SNN model and a
  "reconfigurable ASIC architecture", evaluated on MIT-BIH ECG and DEAP EEG. Source:
  [arXiv 2406.06543](https://arxiv.org/abs/2406.06543). Caveat: from the abstract.
- CinC 2017: 8,528 recordings, 4 classes, ODC-By 1.0, open; best overall score 0.83, four
  teams tied for first; no credentials needed to download. Source:
  [PhysioNet](https://physionet.org/content/challenge-2017/1.0.0/).
- PTB-XL: 21799 records, CC BY 4.0, listed as Database Open Access. Source:
  [PhysioNet](https://physionet.org/content/ptb-xl/1.0.3/).
- AFDB: 25 recordings of 10 h each, ODC-By 1.0, open access. Source:
  [PhysioNet](https://physionet.org/content/afdb/1.0.0/).
- GDPR Art 9(1) prohibits health data processing. Source:
  [GDPR Art 9](https://gdpr-info.eu/art-9-gdpr/). Art 9(2)(h) is the medical-care exception;
  it also needs Union or Member State law or a health-professional contract, plus the
  paragraph 3 safeguards. Caveat: "medical care" is a loose label for it.
- Transfers outside the EU: the Art 46 safeguards route applies absent an adequacy
  decision. Source: [GDPR Art 46](https://gdpr-info.eu/art-46-gdpr/). Caveat: the
  unqualified first wording, that transfers need safeguards, was overstated.

## Tools on the Mac

- yowasp-yosys: Yosys binaries built for WebAssembly, one py3-none-any wheel, "Requires
  Python ~=3.9". Source: [PyPI](https://pypi.org/project/yowasp-yosys/). Caveat: the page
  does not use the words "platform-independent".
- YoWASP runs on "macOS (x86_64 and AArch64)"; Yosys built for WebAssembly is "about half
  the speed of a native build"; Nextpnr WASM is about as fast as native. Source:
  [YoWASP](https://yowasp.org/).
- SkyWater PDK is released under the Apache 2.0 license. Source:
  [skywater-pdk](https://github.com/google/skywater-pdk). Caveat: the README says nothing
  about per-component exceptions.
- OpenSTA: a gate-level static timing verifier, GPL v3; macOS build via Homebrew (CMake on
  Macos/Darwin). Source: [OpenSTA](https://github.com/The-OpenROAD-Project/OpenSTA).
  Caveat: the README does not list report_power, but it lists VCD and SAIF power activity
  inputs, so that absence is not absence of power support. The project is also dual-licensed
  commercially. The first line seen read "OpenSTA engine", not the quoted sentence.
- ORFS uses Docker images; macOS is not mentioned. Source:
  [ORFS](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts).
- difflogic requires CUDA; the Python implementation is "substantially slower" and is
  compatible with device cpu; MIT license. Source:
  [difflogic](https://github.com/Felix-Petersen/difflogic). Caveat: the CUDA implementation
  supports only cuda; a compiled-model export for CPU exists.
- hls4ml backends are vendor HLS tools: Vivado, Vitis, Intel, Catapult and Altera HLS IP
  Gen; no OS requirements stated. Source:
  [hls4ml](https://fastmachinelearning.org/hls4ml/).
- FINN: "we only support Docker-based execution of the FINN compiler at this time". Source:
  [FINN](https://github.com/Xilinx/finn).
- Tiny Tapeout: a tile of about 160x100 um (TT04-TT10), about 1000 digital logic gates, on
  the Skywater 130nm PDK; 6 to 9 months to manufacture; price via calculator. Source:
  [Tiny Tapeout FAQ](https://tinytapeout.com/faq/). Caveat: PCBA, testing and fulfilment
  come after the 6-9 months, up to a year in total.
- Verilator install page: apt-get only; "tested on Apple OS-X". Source:
  [Verilator](https://verilator.org/guide/latest/install.html). Caveat: the page also
  mentions "additional testing on Apple OS-X, FreeBSD and Windows MSVC"; it has no brew
  line.

## Not found

- Other companies and academic work on hard-wired ROM weights (not searched in depth).
- An LLM generating both the model and the circuit.
- Q1 gate counts.
- MCU baseline.
- Q3 guideline.
- Q4, all items (as listed in the medical-edge note).
- Q5b FDA locked wording.
- Tooling note: its not-found items sit in a structured output that is not in the source
  files, so none are listed here.

## Closest published results, read in full

Three papers were read in full (PDF text), and a second reader
checked each claim. Where the check disagreed, its verdict is used.

- **LUT-based 1D-CNN for AF**,
  [arXiv 2605.29994](https://arxiv.org/abs/2605.29994). MIT-BIH
  atrial fibrillation database: 16 of 25 records, about 13,800
  windows of about 42 s, channel 1 only; which 16 is not stated.
  Input is 12-bit, every second sample, 125 Hz. BIG: accuracy 95.8,
  F1 95.6; SMALL: 88.4 and 87.4. Size: 2,844 LUTs, 0 DSP, 871 FF on
  a Spartan-7 S15. Caveats: the train and test split is not stated.
  The 51 us is listed for both designs; the measured 50.88 us was on
  a depthwise-separable model not stated to be BIG. Power, 42 to
  65 mW, is a Vivado estimate. The abstract says no BRAM, but
  Section IV.C has a BRAM input buffer. Search: 73 configurations
  (115 with the first block free), 6 runs of 400 epochs, about 13
  minutes a run on an RTX 8000. This corrects the "F1 up to 95%"
  line above: the abstract says 95.6%.
- **LGN and LUTN for heartbeats**,
  [arXiv 2609.32854](https://arxiv.org/abs/2609.32854). Not an AF
  task: four heartbeat classes on the MIT-BIH Arrhythmia Database,
  48 records, split by patient (DS1 train, DS2 test). Classifier
  3,223 LUTs and 0.46 nJ; preprocessing 17,064 LUTs and 8.25 uJ.
  Caveats: hardware figures are vectorless Vivado estimates at an
  assumed 1 MHz. Each accuracy in Table 4 is the best across depths,
  so one row is not one model. The abstract's 94.41% and jk 0.683
  come from different models. The 1-layer 6-LUTN built in hardware
  scores 94.04 and jk 0.651. Per-class sensitivity of the 6-LUTN: N
  0.998, S 0.007, V 0.869, F 0.003. Depth and temperature appear
  chosen on the test set. This corrects the 94.41% and 0.683 line
  above.
- **AF patch on an FPGA**,
  [arXiv 2508.13181](https://arxiv.org/abs/2508.13181). Own dataset,
  30 people, about 98K samples of 120 s, split 70, 15 and 15
  percent; a split by person is not stated. 7,328 parameters, 14.6
  KByte, iCE40 UltraPlus; sensitivity 0.938 and specificity 0.981
  for the chosen model. Search: 190 generations, 8 offspring each, 30
  epochs per candidate, 220 Pareto individuals; search time is not
  stated. Caveats: 3.81 mW was measured for the whole platform,
  without Bluetooth or storage. No absolute LUT count, latency or
  energy per inference is given. The abstract's "95% accuracy" has no
  source number in any table; Table III's 95.8% and 95.8% equal the
  MIT-BIH column of Table II.
- **Clinical bar, partly confirmed.** AAFP review of a handheld ECG:
  sensitivity 92% and specificity 95% for AF, 233 patients at one
  outpatient clinic, against a 12-lead read by a cardiologist
  ([AAFP](https://www.aafp.org/pubs/afp/issues/2020/1101/p562.html)).
  Other cohorts on that page: 100% and 97% (n=55, AF or flutter);
  94.6% and 92.9% (n=42), a reading within 30 s.
- **Microcontroller candidate.** ESP32-S3, about 180 KB, 9 ms
  latency, binary normal against abnormal, not AF, no Cortex-M, no
  energy figure
  ([arXiv 2606.02256](https://arxiv.org/abs/2606.02256)).
- **FDA wording.** The page says some AI-enabled devices "may also
  adapt over time as new data, information, or experience becomes
  available". It has no "locked" wording
  ([FDA](https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-software-medical-device)).

### Not found

- The clinical accuracy bar: the ESC 2020 30 s rule, NICE MTG64 and
  a PubMed entry were only seen as search snippets; the pages were
  not opened (fetch blocked).
- A Sensors 2025 microcontroller figure (3532 uJ, 143 ms): search
  snippet only; the page was blocked.
- A microcontroller or Cortex-M baseline for AF with inference time
  and energy.
- Code for the AF model of 2605.29994 (the generator tool is open
  source; whether the model is in it is not stated), and any code
  link for 2609.32854 or 2508.13181.
- The 16 records used by 2605.29994, and its train and test split.
- A per-class or sensitivity figure for the headline 95% of
  2508.13181.
- Q4 items of the clinical-bar search were not attempted.
