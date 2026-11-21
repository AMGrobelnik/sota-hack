# Idealab.ai public search: findings (2026-11-21)

## Method (repeatable)

- Headless Playwright (not Adrian's Chrome). Open <https://idealab.ai/#database>, click "Reject all" on the cookie dialog, type the query into the "Describe what you're an expert in" box, press "Show me my ideas". It goes to <https://idealab.ai/idea-query> and POSTs <https://idealab.ai/api/idea-search> with {"query":..,"sectors":[],"capital":[],"limit":10,"filters":{},"includeTotal":true}. No account, no email, no terms accepted.
- Plain curl to that endpoint returns {"error":"visitor-cookie-required"}; it works only from the page (visitor cookie set by page load). I ran 11 of the queries via fetch() inside the loaded page, and Q1 through the UI.
- Brief URL: <https://idealab.ai/idea-details/><id>?from=search. Tabs (Plan, Market & competitors, Founder profile, Lineage & sources) and "Things to watch for" (risks) are visible without login. Only the chat box needs an account ("ACCOUNT NEEDED"). I did not open Founder profile.
- Result fields: id, title, thesis, capital, time to market, similarity (0.3 to 0.47 here, i.e. weak semantic matches), view count. Ranking is embedding similarity; no result matches the shortlist closely.
- 12 queries (match counts): Q1 "AI scientist automated scientific discovery" (1,514); Q2 evolutionary program search where a language model proposes programs and tests score them (1,627); Q3 fast LLM inference tokens per second hardware (660); Q4 in-memory compute memory bandwidth bottleneck accelerator (1,300); Q5 routing workloads across AI models and chips (1,760); Q6 hardware-aware AI for scientific computing parallel simulation (1,783); Q7 parallel simulation for medical device design blood flow (1,470); Q8 reduced-lead ECG deep learning (1,525); Q9 analog computing low-precision noise tolerance neural network inference (913); Q10 Ising machine combinatorial optimisation hardware (1,348); Q11 AI for clinical research with heavy GPU compute (1,215); Q12 autonomous agent tuning scientific simulation code (1,434).
- Caveat: these are business ideas (a customer, a price, a pilot), not code or datasets. Competitor names are the generator's, not verified by me. The "sources" are mostly patents/papers/news that fed the idea; titles shown are seed sources.

## Entries (all links <https://idealab.ai/idea-details/><id>)

Quotes are exact from the brief text.

### AI scientist (Q1)

- 746174 Closed-Loop Scientific Discovery Engine. Summary: "turns private datasets, literature, simulations, and prior experimental results into ranked mechanistic hypotheses and executable validation plans". Why now: "AI systems have improved at long tasks, code writing, and working in groups, while needing less human guidance." Competitors (6): Plex Research (AutoPlex), Omic, Due Science, Owkin, insitro, Generate Biomedicines. Bet/risk: "machine-generated hypotheses produce more non-obvious, experiment-worthy findings than expert ideation or ordinary literature search". Sources: "45 sources, 3 patents, 9 scientific papers, 33 news articles" (titles not read). $400K, 5 months.
- Other Q1 hits (summaries only, briefs not opened): 34928 Evidence-Grounded Literature-to-Lab Experiment Engine; 1512506 Auditable AI Copilot for Experimental Science; 1301490 Falsifiable Hypotheses for Drug Discovery. Also seen in list: "MethodBridge for Scientific AI", "Autonomous Model Improvement Workbench", "Closed-Loop Experiment Planner for Scarce Beamtime" (ids not captured).

### Evolutionary program search (Q2)

- 674119 Evolution Engine for Production AI Workflows. Summary: "turns prompt and agent development into a controlled search". Why now: "Cheaper model runs and better small scoring programs make thousands of trials affordable". Competitors: Promptic, EigenPrompt, FastRouter, Google Cloud. Risk: "The cheap scorer ranks changes poorly on real tasks, so customers cannot trust the improvements." Source cited: "Evolutionary Content Generation via Multimodal LLM-based Fitness Evaluation" (paper, 2026), plus "16 sources, 8 patents, 4 scientific papers". Closest to shortlist 1 but is prompt tuning, not program search. No named AlphaEvolve/FunSearch/OpenEvolve in what I read.

### Inference speed, memory bandwidth, routing (Q3 to Q5)

- 1544979 Memory-First HBM Inference Accelerator: "places compute units beside high-bandwidth memory"; "accelerators waste power moving model weights during transformer decoding". Competitors named: Samsung, SK hynix. $45M, 30 months. Only the intro read.
- 893605 Memory orchestration for AI accelerators: "High-bandwidth memory ... now needs closer watching". Intro only.
- 456158 Switchboard: Vendor-Neutral Inference Runtime. Competitors named in intro: NVIDIA, Runway. Intro only.
- 1707504 Overlap Runtime for Distributed AI. Competitors in intro: TetriServe, NVIDIA. Intro only.
- Listed, not opened: 601919 On-device LLM runtime; 1231308 On-Accelerator Predictive Prefetch Controller; 629213 Elastic Memory Fabric; 705113 Inference Memory Efficiency Control Plane; 1208486 SparseMarshal; 741396 Memory Virtualization Runtime; 672400 Agent Compute Control Plane; 1590432 Inference Capacity Control Plane; 1394869 Compute Arbitrage Router for AI Agents; 1570157 CacheFlow Inference Control Plane.
- Briefs 893605, 456158, 1544979, 1707504 loaded with only the intro text in my extraction (Why now, risks, competitors, sources came back empty; page layout differed or did not finish loading). Not read, not claimed absent.

### Parallel simulation, medical devices, ECG (Q6 to Q8)

- 1730639 Parallel Runtime for Particle Simulation. Summary: "hardware-portable runtime that accelerates particle-based scientific and engineering simulations" (SPH and DEM). Why now: "Cheaper GPUs ... and better code-writing tools make particle simulation speedups easier to deploy". Competitors: Ansys Rocky, Siemens Simcenter EDEM, Prometech. Risks: "Numerical accuracy concerns keep customers from trusting the faster results." Sources: 7 (3 patents, 4 papers); seed "GPU-accelerated particle solver for biomechanics on edge devices" is the fed-idea title.
- 1153998 PrecisionMap for Scientific Accelerators. "analysis ... showing where code fits and what tests a move needs". Why now: "Artificial intelligence processors have pulled ahead on some tasks, while scientific codes still need accurate number work, fast data movement, and communication between processors." Competitors: Rescale (Compute Optimizer), Expanse; also Arm named. Risk: "The analysis may fail to produce useful, accurate placement advice". Source: news "Uncle Sam's next big supercomputer might use something more exotic than GPUs" (2026).
- 1586912 Patient-Specific Cardiovascular Device Simulator. "combine medical scans with blood-flow physics to compare device designs"; LVAD. Why now: "Better heart-flow modeling, faster image reading and evidence near animal-study accuracy make virtual device tests more credible". Competitors: MedStar Health (patient-specific pump model, seeks partner), Virtonomy, Cardio4D. Risk: "Per-case computing costs stay high, so simulation services cannot earn enough." Sources: 3 (2 patents, 1 paper).
- Listed, not opened: 637829 Digital twin for blood-contact circuits; 575374 Hemodynamic digital twin; 26738 Cardiovascular Virtual Evidence Foundry; 639190 Vascular Digital Twins; 1595485 Virtual Test Bench for Medical Devices.
- 582238 ECG annotation and arrhythmia-endpoint platform. "Efficient transformer models ... label heartbeats in long recordings at lower cost". Competitors: CardiacCloud AI, Cardiomatics, Philips Cardiologs. Risk: "Noisy recordings defeat the service against expert readings". Sources: 22 (7 patents, 12 papers, 3 news); first paper "Refined self-attention transformer for ECG-based arrhythmia detection" (2024).
- Listed, not opened: 653362 Offline Cardiac Diagnostics; 1570272 Clinician-Governed ECG Intelligence; 773634 RapidLead Prehospital Cardiac Diagnostics (a multi-lead platform, intro cut). Q8 produced no result that mentions reduced or subset leads in the title or the first ~100 characters of the summary (I did not read full texts of the listed ones).

### Analog, low precision, Ising (Q9 to Q10)

- 1337595 Adaptive Precision Co-Training Engine. "jointly selects digital bit-widths and analog" settings. Competitors: IBM AIHWKIT (analog hardware-aware training with "weight noise, drift, quantization"), Rockpool, Analog Compute Systems. Risk: "Chipmakers keep their device models private". Source seeds not relevant (IoT).
- 585845 PrecisionBound for high-stakes model inference. "mixed-precision strategy" for medical imaging with FP8; "tests each layer, selects its number format". Competitors: Intel OpenVINO NNCF, MedPTQ, NVIDIA TensorRT. Sources: 6 (5 patents, 1 paper); papers cited: "Readout scheme for PCM-based analog in-memory computing with drift compensation" (2024), "Phase change memory drift compensation in spiking neural networks using nonlinear current scaling" (2024), "Bayesian neural networks via phase-change memory: exploiting noise, mitigating drift" (2025). These three are directly reusable for shortlist 5.
- 1512870 Reliability Cloud for Analog Inference. "A device can give wrong answers as chips age, heat up, or meet unfamiliar inputs." Competitors: SocketRun, Analog Devices, Arithmos AI. Risk: "Analog inference stays pre-commercial".
- Listed, not opened: 975832 Precision Autopilot for Neural Inference; 902290 Adaptive Threshold IP for Analog AI Tiles; 1550146 Low-Power ADC Calibration IP.
- 1749764 Ising: Universal Ising Compiler. "converts constrained business and scientific [problems]" for Ising machines. Competitors: D-Wave Ocean, Fixstars Amplify, Kaiwu, qubocompiler, Toshiba. Risk: "Ising machines stay experimental". Sources 8 (4 patents, 4 papers), e.g. "Josephson parametric oscillator-based Ising machine for combinatorial optimization" (2024).
- Listed, not opened: 1346506 Custom Photonic Ising Accelerators; 1701436 Ising Accelerator for Chip Place-and-Route; 1222848 Dimensional Annealing Compiler; 1462414 Auto-Tuning IP for Ising Solver Platforms.

### Q11, Q12 (clinical compute, agent tuning simulation code)

- 602101 Adaptive-resolution runtime for medical imaging AI ("diagnostic-equivalence-preserving inference runtime"), 79394 ReproCompute Federated Research Cloud, 1404132 Spillover Runtime. Not opened.
- Q12 returned autonomous-vehicle and robot tuners (588961, 1540581, 1726379 OpenTune). No result about tuning blood-flow solvers: no result for query "autonomous agent tuning scientific simulation code" (top 6 by title/summary).

## Per shortlist idea

1. Parallel AI scientist: closest 674119 (prompt-evolution business, competitors Promptic/EigenPrompt/FastRouter) and 746174 (competitors Plex Research, Omic, Due Science, Owkin, insitro, Generate Biomedicines). Nothing names a tokens-per-second vs discovery-speed measurement. Useful risk: cheap scorer ranking unreliably; "hypotheses ... more non-obvious ... than expert ideation".
2. ECG lead subsets: no result for query "reduced-lead ECG deep learning" whose title/summary shows lead subsets (only top 6 listed). 582238 competitors CardiacCloud AI, Cardiomatics, Philips Cardiologs; risk noisy recordings, regulators treat assistive service as diagnosis tool.
3. Blood-flow code tuning: 1586912 (MedStar, Virtonomy, Cardio4D; risk "Per-case computing costs stay high") supports the "why compute matters"; 1730639 and 1153998 for solver speed-up, Rescale, Ansys Rocky. No agent-tuning entry (Q12).
4. Optimiser chip precision/noise: 1749764 (D-Wave Ocean, Fixstars Amplify, Toshiba), 1346506 photonic Ising (not opened). Risk: "Ising machines stay experimental".
5. Analog LLM noise: 585845 (three PCM papers), 1337595 (IBM AIHWKIT, risk of private device models), 1512870 (silent errors). None targets language models specifically.

## Up to 8 candidate projects

1. 1337595 + 585845: sweep bit-width and noise level of an LLM or small model with simulated analog weight noise (AIHWKIT-style), packed in parallel on one GPU; accuracy-vs-noise curve plus energy proxy. 24-hour build: noise injection in PyTorch, grid of thousands of settings batched. Medical angle: use a medical-imaging or ECG model as the tested network (585845 frames it).
2. 674119: parallel evolutionary search loop with LLM proposals and tests as scorer; vary proposals in flight and tokens/second; plot discovery curve. Medical angle: target a task such as ECG feature code or ODE parameter fitting.
3. 1730639: parallelising an SPH/DEM-style particle solver; the pitch of "accuracy reports". Biology: blood or cell flow as particles.
4. 1586912: lumped or 1D blood-flow ensemble over many patient parameter sets, one GPU job; visual output. Medical student can supply parameter ranges (clinical risk: "Per-case computing costs stay high").
5. 1153998: profile a small scientific code on CPU/GPU, advise placement and check accuracy; visual roofline plot (memory bandwidth bottleneck).
6. 1749764: map a small optimisation (for example sparse lead selection for ECG) to an Ising/QUBO form, solve with parallel annealing on GPU, compare with a classical baseline. Medical: choosing the best lead subset is a binary selection problem.
7. 582238: train many small models over subsets of ECG leads in one batched GPU job (shortlist 2), using published lead-count arrhythmia transformers as the baseline.
8. 746174: small closed-loop hypothesis tester on public biomedical data, with provenance log.

## Pitch material

- Why now: 746174 "AI systems have improved at long tasks, code writing, and working in groups"; 674119 "Cheaper model runs ... make thousands of trials affordable"; 1153998 "Artificial intelligence processors have pulled ahead ... while scientific codes still need accurate number work, fast data movement"; 1544979 "accelerators waste power moving model weights during transformer decoding".
- Named competitors: AI scientist: Plex Research, Omic, Due Science, Owkin, insitro, Generate Biomedicines. Prompt/agent search: Promptic, EigenPrompt, FastRouter, Google Cloud. Inference hardware: Samsung, SK hynix, NVIDIA, Intel OpenVINO, TensorRT. Analog: IBM AIHWKIT, Rockpool. HPC placement: Rescale, Ansys Rocky, Siemens EDEM. Ising: D-Wave, Fixstars, Toshiba.

## Not read

- Briefs 893605, 456158, 1544979, 1707504: only intro captured (Why now/risks/competitors/sources came back empty).
- Founder profile tab for every brief; ids for several Q1 hits; full lists beyond top 6 per query; many listed entries unopened. Sources are shown as counts plus a few seed titles; full source lists need expanding in the page.
- Chat on each idea needs an account; not used.
