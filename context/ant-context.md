# Ant context: everything we know (Antonio's notes)

Compiled Sat 21 Nov 2026, during the hackathon, from SoTA's emails and Luma page, the event Discord (read 14:20), the slide shown on the day, the team's notes, this repo and public web research. Guesses are marked as guesses. Nothing here is from inside the judges' room.

Contents: 1 Essentials · 2 Main idea · 3 Judges and mentors · 4 Sponsors · 5 The prize (Manchester) · 6 Past SoTA winners · 7 The field · 8 All other ideas · 9 Sources

---

## 1. Essentials

| | |
|---|---|
| When | Sat 21 Nov 11:00 to Sun 22 Nov 18:00 |
| Where | Halkin, 1-2 Paris Garden, London SE1 8ND (first advertised as King's Cross) |
| **Code freeze** | **Sun 14:45** (14:45-15:00 judges' briefing and demo setup) |
| Judging | Sun 15:00-16:30 team demos · 16:30-16:50 deliberation · 16:50-17:00 winners |
| Demo length | Not announced. About 89 people in 90 minutes: plan a 3-minute pitch that can stretch |
| Prizes (cash) | 1st £5,000 + demo slot and panel seat at ARIA's AI for Science Summit, Manchester, Thu 26 Nov · 2nd £2,500 · 3rd £1,000 |
| Compute | Not announced. Five GPU questions unanswered on Discord. Only statement: "Yes bring your own hardware!" |
| Team size | "We usually recommend teams of up to 4 max" (SoTA, 3 Nov). We are 3 (Adrian, Antonio, Oran) |
| Travel refund | Actual receipted public-transport costs, up to £200 per person, paid after the hack; no accommodation |
| Contacts | contact@ilikethefuture.com · Discord https://discord.gg/jpUtFsVQq · hosts Jamie and Matvey |

### Schedule (SoTA on Discord, 17 Nov)
**Saturday:** 11:00 arrivals and team formation · 11:50 SoTA intro · 12:00-12:30 talks from Callosum, Inherent and Fractile · 12:30 lunch · 13:00-18:00 hacking · 18:00 dinner · 19:00 onwards hacking continues.
**Sunday:** 09:00 breakfast · 09:30-12:30 hacking · 12:30 lunch · 13:00-14:45 final hacking, testing, demo prep · 14:45-15:00 judges' briefing and setup · 15:00-16:30 demos and judging · 16:30-16:50 deliberation · 16:50-17:00 winners and closing.

### Judging criteria (slide shown on the day)
1. **Correctness and assumptions:** preserve intended behaviour; explain and justify simplifying assumptions.
2. **Fundamental reshaping:** rethink the problem to expose opportunities for parallelism.
3. **Meaningful speedup:** compare performance with a credible, relevant baseline.
4. **Scientific value:** useful results, sound methods, convincing technical evidence.
Informative negative results count: a well-explained failure to achieve a speedup can still win a prize.

### Rules that exist
- **Pre-written code is allowed** if you say what was done on the day and what was not: "Judges will be suspicious if you don't" (Matvey, 17 Nov). Keep `BUILT-TODAY.md` honest, show it on a slide, name every library.
- Own hardware allowed. Some starter data for the three example challenges was promised.
- Under-18s need written guardian consent and must leave by 22:00 Saturday.

### Still unknown: ask Jamie or Matvey
1. **Is bring-your-own-idea still allowed?** The intro talk mentioned only the three example challenges; a participant asked at 12:58 Sat, unanswered.
2. **Does an engineering problem count?** "Pure natural science, or could electrical engineering work?" (khwleed, 17 Nov), unanswered. Matters for the chip idea.
3. GPUs or credits, and how to get them ("Nadina" was named as a contact; no trace on Discord).
4. Submission format and deadline (repo, slides, form).
5. Demo length and format (stage or walk-round), and who the judges are.

### The brief
Pick a scientifically relevant computational problem, rethink it for massively parallel hardware, build it, benchmark against a meaningful baseline, explain what science it enables. Example challenges: flood uncertainty (thousands of rainfall scenarios), faint asteroid detection (stacking images along motion paths), molecular pose search (millions of ligand poses). Suggested routes: expose existing parallelism, rethink algorithms, change the representation, cross a computational threshold.

---

## 2. Main idea: AI-assisted chip design for medical devices

### Concept (team notes)
- A medical sensing device has sensors, a housing and a core chip. The chip does one job for one application: runs a small model, plain ML, or only combines sensor inputs, as efficiently as possible.
- We build the **environment**, not the chips: a user writes a prompt, the system spins up agents, proposes candidate chip designs, simulates and validates them, iterates, outputs the best design. Views: design stage (ideation, testing, reporting), live agent commands, cost tracking, a chip sketch always visible; the user can pause or redirect.
- Privacy: the model is wired into the chip, so the device works offline and patient data stays on the device. **Do not claim the law forbids cloud processing** (unchecked; GDPR Art 9(2)(h) allows health processing for medical care with safeguards).
- GPUs both simulate the chip and run the small models.
- Adrian's AI-scientist environment was built before the event (disclose it).

### The demo (repo README)
Prompt: *"an atrial fibrillation (AF) detector from a single-lead ECG, with as few logic gates as possible, at the clinical accuracy line."*
1. An AI scientist proposes tiny networks and input choices (sample rate, bits).
2. Thousands are trained at once on the GPU (the parallelism; baseline: one at a time).
3. Winners are compiled to a gate circuit with fixed weights.
4. The circuit is checked bit for bit against the model on unseen patients.
Result: a curve of accuracy against gate count, with Oran's clinical line and where they cross. Visual: the gate circuit lighting up on a heartbeat.

Roles: **Adrian** environment and GPU batch · **Antonio** the views (design stages, accuracy curve, circuit lighting up) · **Oran** the clinical accuracy line and which errors matter.

### Mapping to the criteria
| Criterion | What we show | Make it airtight |
|---|---|---|
| Correctness | Circuit = model bit for bit on unseen patients | Show a ✓ badge per test record; state assumptions (sample rate, bits, which leads); patient-level split, no leakage |
| Reshaping | Thousands of designs trained as one GPU batch; agents propose in parallel | Diagram: one-at-a-time loop vs batched search |
| Speedup | Designs per hour vs one at a time | Same code, same GPU, batch size 1 vs N; plus CPU baseline; median of repeats; include data-loading time. Circuit vs microcontroller only as a labelled estimate |
| Scientific value | Accuracy vs gate count with the clinical line | Compare with published AF/ECG hardware (below); say where we lose |

**Headline idea:** time to a clinically acceptable design = designs/hour speedup × how few designs the agent loop needs vs random search at the same budget.

### Published comparators (checked unless marked)
- Wearable AF patch, hardware-aware NAS on FPGA: 95% accuracy at 3.8 mW, 3+ weeks continuous (arXiv 2508.13181).
- LUT-based 1D-CNN for AF: F1 up to 95%, 2,844 LUTs, no DSP/BRAM, MIT-BIH, Spartan-7 (arXiv 2605.29994).
- Logic-gate/LUT ECG classifier: 94.41%, 8.25 µJ (arXiv 2609.32854; an earlier version was withdrawn).
- SparrowSNN ECG ASIC: 98.29% on MIT-BIH, 31.39 nJ per inference, 6.1 µW (arXiv 2406.06543). EKGNet analog: 10.96 µW.
- Differentiable logic gate networks: 98.47% MNIST at 384k gates; 97.69% at 48k (Petersen 2022).
- Tiny Classifiers: ≤300 gates on tabular data (arXiv 2303.00031).
- Prior art to acknowledge: Taalas HC1 (Llama 3.1 8B hard-wired), hls4ml, FINN, LogicNets, PolyLUT, NeuraLUT, AlphaEvolve's Verilog for a TPU. LLM agents for RTL are busy research in 2026: VeriAgent (with a power/performance/area agent), agentic formal verification >95% coverage, HLS-based agent flows 2.6x better than direct RTL (ICCAD '26). **Our claim is the automated parallel design loop plus the accuracy-vs-gates result for a clinical task, not "first to compile a network to gates".**

### Data and tools
- Open, no login: CinC 2017 (8,528 single-lead recordings, 4 classes, best score 0.83, four teams tied), AFDB (25 × 10 h), PTB-XL (21,799 records).
- Tools: yowasp-yosys (Yosys via pip, runs anywhere, half native speed), Verilator, difflogic (needs CUDA), FINN and OpenROAD flow (Docker), Tiny Tapeout (~1,000 gates per tile on SkyWater 130 nm; 6-9 months to fab: a nice "you could actually make this" slide).
- GPU circuit simulation context: NVIDIA RTLflow 40x vs an 80-thread CPU with 65,536 stimuli; NVIDIA GEM 5-40x vs CPU simulators (about 6x vs 8-thread Verilator).

### Why it fits the room
- Chip and verification mentors (Fractile's on-site verification engineer, ex-Graphcore architects at Fractile and ARIA).
- Callosum: work split across hardware; Akarca: "The real end goal of scaling heterogeneous compute is to make new discoveries."
- Inherent: an AI scientist that proposes, tests, learns, and reports faithfully.
- ARIA Scaling Compute: cheaper inference hardware. Hugging Face: small models.
- Earlier research: always-on edge sensing is where specialised low-power chips win first (Innatera, BrainChip ship at µW to mW).

### Risks
- Not allowed? (own idea / engineering) → fallback: flood uncertainty (section 8).
- Too generic: always lead with the AF demo and its numbers, never the platform.
- Chain not proven end to end (feasibility test on Adrian's Mac).
- Compute unknown: size the batch to what we actually have.
- Overlapping teams on Discord: tobi ("massively parallel scientific falsification, autonomous research swarms").

### Views (Antonio)
Design stages · live agent log · accuracy-vs-gate-count curve with the clinical line · circuit lighting up on a heartbeat · **designs/hour counter vs the one-at-a-time baseline** · **bit-exact ✓ badge** · cost tracker · the built-before / built-here split.

### Pitch order that fits the judges
Correctness check → fair baseline → speedup (and memory-vs-compute if measured) → the clinical result and curve → limitations → built-before / built-here. Name a clinician (Oran) for the clinical line.

---

## 3. Judges and mentors
**No judges or mentors have been named anywhere** (Luma, Substack, Discord; Discord has no roles). We were told most judges are AI-for-science people, unlikely to have biology or medical expertise (so the clinical part needs one clear slide and Oran's line, not jargon), and that some mentors are chip and evaluation experts. Past SoTA panels: Jamie + someone from the main sponsor or programme + one or two outside experts (from SoTA Letters VIII and a LinkedIn recap; the repo's judges note could not verify this).

### Most likely in the room
| Person | Role | Why | What they value |
|---|---|---|---|
| Jamie Croucher (@jamiec_24) | SoTA co-founder and director | On every past SoTA panel found; shares two past events with Antonio (Hyde Park picnic, Claude Hackathon at Imperial) | End to end, real use, evidence |
| Matvey Boguslavskiy (@matbogus) | SoTA co-founder and director | Answered the code rules | Honest built-today disclosure |
| Aayush Chadha | ARIA Frontier Specialist, AI for Science | Has spoken at SoTA events | "A step-change, not a five percent improvement" |
| Danyal Akarca | Callosum CEO | Publicly backed the event | Speed that leads to discoveries |
| Jascha Achterberg | Callosum CTO (ex-Intel chips) | Technical candidate | Work split across hardware, trade-offs shown |
| Clara (probably Clara Hollowood; unconfirmed) | Fractile chip verification engineer | On site helping | Proof that results are correct |
| Edward Hughes (guess) | Inherent Chief Scientist | Likely gave the talk | Faithful results, research taste |

### Chip and hardware experts
Alan Alexander (Fractile Chief Architect, ex-Graphcore, NVIDIA) · Paolo Toccaceli (ARIA Scaling Compute technical specialist, ex-Graphcore) · George Constantinides (Imperial; reportedly scientific director of ARIA's Scaling Inference Lab, unverified) · Suraj Bramhavar (ARIA Scaling Compute Programme Director, electrical engineer) · Jascha Achterberg.

### Evaluation and verification experts
Clara Hollowood and Harry Sim (Fractile verification) · Damon Falck (Inherent, co-wrote the replication benchmark) · Ant Rowstron (ARIA Chief AI Scientist: "benchmark hygiene matters") · David Page (Fractile AI lead; possibly the author of the fast CIFAR-10 GPU training work, unconfirmed).

### AI for science
Anja Surina (Inherent, ex-DeepMind AlphaEvolve) · Kaloyan Aleksiev (Inherent co-founder, infrastructure) · Georgia Channing (Hugging Face AI for Science lead) · Pranay Shah (ARIA Head of Special Projects; spoke at SoTA) · Edith-Clare Hall (ARIA Frontier Specialist, robotics; moderates the Manchester winners' panel).

### Likely mentors
Callosum engineers Adrian Bertagnoli, Carlos Segarra, Matthieu Bou; SoTA Fellow Michal Karlubík.

### Senior, less likely to attend
Walter Goodwin (Fractile CEO; manifesto: time-to-result is the real limit; memory bandwidth "has failed to scale") · Tantum Collins (Inherent CEO) · Louis Kirsch (Inherent) · Dave Lewis (ARIA Chief Science and Technology Officer) · Alex Obadia (ARIA; past SoTA judge).

### What the whole group rewards
1. Faithful, verified correctness: show the check first.
2. A fair, relevant baseline and an honest list of limitations.
3. Time to result; whether code is limited by memory bandwidth or compute.
4. Speed that leads to a discovery; work split across hardware where it fits.
5. A step change, not a few percent.
6. Open code and data (Hugging Face Hub with cards).
7. Bonus: ARIA's Scaling Inference Lab tests pipeline parallelism on older, cheaper GPUs (Cluster 1) and Callosum's mixed-hardware orchestration (Cluster 2).

---

## 4. Sponsors

| Organisation | What it is | Why it matters |
|---|---|---|
| **SoTA** | London community of ~600 scientists, engineers, founders; weekend deep-tech hackathons; sotaletters.substack.com | Grand Prizes go to an end-to-end working system with a real use and evidence |
| **Callosum** | London, founded 2025 by Cambridge neuroscientists; splits AI work across different chips; USD 100M seed (Atomico); Cerebras partner; tech partner for Cluster 2 of ARIA's Scaling Inference Lab | Heterogeneous compute → discoveries |
| **Fractile** | London/Bristol inference chips (DRAM stacked on logic); USD 720M Series C (Nov 2026, ~USD 7B); first chips 2027 | Memory bandwidth bottleneck |
| **Inherent** | King's Cross AI lab, ~12 people; USD 50M seed; AI scientist Faraday | Faithful, verified results |
| **ARIA** | UK Advanced Research and Invention Agency | Scaling Compute (AI hardware >1000x cheaper), AI in Science, £65M Olfactory Perception programme |
| **Hugging Face** | Named only in SoTA's 9 Nov newsletter | Open datasets and small models |

**Talks on the day (team notes).** Fractile: speed is the main dividend in AI; FLOPs grew ~1,000,000x in 40 years, memory bandwidth ~40x; DRAM stacked on logic vs SRAM-based Groq/Cerebras (fast but expensive, poor at long context); volume hardware by end of next year; two staff on site, Clara helping. Inherent: AI should augment human scientists; "living collaborator" models that decide when to interrupt or act; trains its own models; a 27B model beat frontier models at replicating papers; small planning model delegates coding to external agents; hiring in post-training, infrastructure, science.

**Inherent's paper:** "Training AI Scientists to Replicate Research", arXiv 2608.13331 (13 Aug 2026). Replica benchmark: 310 figure-replication tasks from 100 papers. Faraday (Qwen3.6-27B post-trained, handing coding to parallel Codex agents) beats Claude Opus 4.8 and GPT-5.5 on 60% of held-out AI-for-science tasks. Headline example: a rival faked molecule generation by pulling molecules from the dataset; Faraday decoded new ones.

---

## 5. The prize: AI for Science Summit, Manchester (Thu 26 Nov)
- Renold Building, 32a Altrincham St, M1 7JR; about 12:00-17:00; free, public registration full. Hosts: Conception X, Turing Innovation Catalyst Manchester, ARIA. (Not the Cambridge AI for Science Summit at Churchill on 24 Nov.)
- Winners demo and join the panel **"Solving for Massive Computation & Inference for SoTA Science"**, moderated by Edith-Clare Hall (ARIA).
- Speakers: Dave Lewis (ARIA CSTO, ex-DARPA), Erwann Le Lannou (UK Sovereign AI fund: up to 1M GPU-hours per startup, route to equity; invested in Callosum), Leah Morris (Encode fellowship, Pillar VC x ARIA), Liz Scott MBE (Turing Innovation Catalyst), founders from Boltz, Prima Mente, twig, Biographica, Cultivarium; academics Dave Topping, Nathan Skene.
- SoTA panel "New Instruments and Hardware for AI-enabled Science" (Jamie): David Jordan (Living Physics Lab; ARIA seed "Cell Learning for Natural Computing"), Jaime Garcia (Superposition Bio), Dean Thomas (Cronin group, Glasgow).
- Evening: Frontier Robotics Happy Hour, Armnet x SoTA, 17:30, The Anthologist, St Peter's Square. Venture Café 17:00-20:00 at Sister.
- Side events listed on the summit calendar: Constructor Labs "Benchmarking AI Scientists", Digital Catapult "The Next Frontier: AI for Science", Nucleate, a Pillar VC breakfast, Encode, Planet A drinks.
- Funding routes that fit a GPU project: Sovereign AI compute; a warm intro to ARIA's Scaling Inference Lab (via Hall or Lewis); Encode (rolling problem and dataset submissions). No current ARIA open call is about compute.
- If we win: it clashes with Antonio's RSP session on compute resources at 10:00 that day.
- Value: a stage in front of ARIA's senior technical lead, a Sovereign AI investor and compute-hungry bio founders. Appears to be the first SoTA prize with an ARIA stage.

---

## 6. Past SoTA winners (the pattern)
- Trust Everything, Everywhere (with ARIA, Mar 2026): MineTrust (mine clearing verified with zero-knowledge proofs); Technical Excellence ClawdBoat (later presented to BAE).
- Embodied Intelligence (Jun 2025): low-cost lab-automation gantry (became London Biocompute).
- Weather Control (2025): a tool explaining climate interventions' cooling and cost; Technical Excellence: GNN humidity simulator.
- Human Augmentation (Jul 2025): Thomas.Orb (expert intuition into Bayesian distributions).
- Rebooting State Capacity (Apr 2025): Treasury Busters.
- Pattern: working end to end, a clear real-world use, evidence it works. Deep technical work often gets a separate Technical Excellence prize.

---

## 7. The field (Discord, 89 members)
- **Crowded:** neuroscience and brain modelling (4), molecular and chemistry (5).
- **Untouched:** docking, flood, asteroids, ultrasound, cardiac, chip design.
- **Close angles:** tobi (massively parallel scientific falsification, research swarms), Sebastien Dupre (diffusion surrogates for uncertainty in PDEs/CFD), Fisherman (pose search; "clear benchmarks NOT just headline speedups").
- **Possible 4th member** (GPU and hardware skills, looking for a domain problem): Pierre Khoury (ex-Intel timing; built "tickbound", a GPU kernel-timing profiler), Akshat (GPU/TPU kernels at Luma AI), **ayman (ex-Arm CPU/SoC formal verification, FPGA: a natural fit for the chip idea)**, Gursukh (distributed inference).
- A competing team's public repo: github.com/atiladeokegab/sota-parallelism-nov21 ("Team Dry Lab").

### Discord in full (read Sat 21 Nov, ~14:20)
- **Server:** "Scientific Parallelism Hack", created ~2 Nov, 89 members. Channels: #general (the only busy one), #introductions (~18 intros), #travel-accommodation (3 messages), #links_chat, #food, #pics_videos (all empty), one unused voice channel. No announcements, rules, compute, submissions, judging, mentors or sponsor channels; no pins, threads, events or roles.
- **Organiser accounts:** "SoTA" (sota_2024, server owner) and Matvey (matbogus). Only five organiser messages in total (team size, under-18s, schedule, code rules). **No organiser post since 17 Nov**, including through Saturday's arrivals.
- **Zero mentions** of ARIA, the Manchester summit, Hugging Face, Nadina, prize details or credits (beyond one unanswered question). Callosum, Inherent and Fractile appear only in the schedule line.
- **Unanswered questions:** GPU level and which GPUs (niki 3 Nov; Joey Bryson 12 Nov; Ani 21 Nov 13:45); GPU servers and chat credits (mcclain98, 21 Nov 14:11); pure natural science vs electrical engineering (khwleed, 17 Nov); team size again (Pierre Khoury, 21 Nov 04:33); remote participation (Oliver, 21 Nov 12:10); bring-your-own-idea still allowed (David K., 21 Nov 12:58); Saturday-morning door and lateness questions (DonYin, chris). Travel refund "after the hackathon" was answered by a participant (Warten404), not an organiser; the Luma blast confirms it officially.
- **Everyone's stated interests** (no team or project names posted):
  - Fisherman (Don): molecular pose search, GPU stochastic simulation and rare-event estimation; wants "clear benchmarks NOT just headline speedups".
  - eshnil (Nilesh): surrogate models for materials and chemicals; Lean-based physics verifier.
  - Galaxy (Yong): GPU molecular simulation, computational biology; real-time surgical instrument detection.
  - Helios: protein foundation-model interpretability; own compute; embedded C and hardware.
  - Hibiki Matsuyama: quantum and molecular spin dynamics.
  - Sebastien Dupre (Seb): parallelising diffusion-model surrogates for uncertainty in PDEs/CFD.
  - tobi: alternating neural integrators; massively parallel scientific falsification; autonomous research swarms.
  - Nick: generative model of brain development. DonYin (Don): neuroscience. wjason00 (Jason): computational brain modelling. alyo_ (Ahmed): biomedicine and neuroscience with RL.
  - Oscar Klemenz: astronomy (CNNs for star clusters); works on AI evaluation.
  - Theo: testing independence before parallelising.
  - Pierre Khoury: ex-Intel precision timing and network hardware; "tickbound" GPU kernel-timing profiler; seeking a team.
  - Akshat: GPU/TPU kernel optimisation at Luma AI; seeking a team.
  - ayman: ex-Arm CPU and SoC formal verification, FPGA; seeking a team.
  - Gursukh: distributed inference; seeking a domain expert.
  - Warten404 (Artiom): cybersecurity, compute architecture. Joey Bryson: Rust/C/Python, wants to join a team.

### Luma page extras
- Observer tickets £25 (approval required). Host blasts: 27 Oct travel form; 2 Nov Discord + travel up to £200 per person, processed after the hack; 20 Nov reminder.
- Jamie's profile: "Co-founder, SoTA"; Matvey's: "SoTA, robots, space, hackathons".
- Upcoming SoTA events: Frontier Robotics Happy Hour (Armnet x SoTA), Manchester, Thu 26 Nov 17:30; SoTA Maritime Autonomy Frontiers Night, Portsmouth, Fri 4 Dec 18:00.

### Opening talk (team notes)
- Judging at 3 p.m. the following day. **Criteria as spoken: correctness of assumptions, novelty, meaningful speedup, scientific value** (the slide says "fundamental reshaping" where the talk said "novelty": cover both).
- Credits available for parallel computing access: ask the organisers (or Nadina) for the link.
- A companion event in Manchester around the same time.
- Inherent's speaker offered to post a link to the replication paper (arXiv 2608.13331, section 4).

### Team track record (for credibility, if asked)
- Antonio and Adrian won the build track at the Oxford and Cambridge AI Race (25 Oct 2026, King's College Cambridge) with The Crophecy: 96 LLM agents betting on EU crop prices, forecasts committed on Solana, leakage-guarded backtest.
- Antonio: Hack the Future winner (2024, 3D digital twin with Three.js and graph neural networks); Notion London Hackathon People's Choice (Mar 2026, NotionOS); finalist at Iterate London RL (liquid neural networks for drone control, beat an MLP baseline) and the xAI Grokathon (Grok.dad).
- Oran ran an AF screening programme (sets the clinical line).

---

## 8. All other ideas (status Sat evening)
Fallback rule if the main idea is not allowed or stalls: own idea allowed + strong GPU → ultrasound; own idea allowed, limited GPU → thermal; only the three examples allowed → **flood**.

1. **Transcranial focused ultrasound under skull uncertainty** (j-Wave, JAX). Thousands of plausible skulls in one batch; probability the beam hits and heats the target; gradients to optimise transducer settings. Benchmark with known answers: Aubry et al. 2022 (ITRUSST; 9 cases; Zenodo 6020543; 11 codes agree within 10% pressure, 1 mm position). Baseline: k-Wave's own CUDA code on the same GPU. Novelty risk: Stanziola, Pineda-Pardo and Treeby (UCL, j-Wave authors) already published skull-uncertainty estimation (arXiv 2212.04405), so the angle must be robust planning across skulls or showing where their linear shortcut fails. Pitch numbers: sound speed needs <4% error; 0.1 mm skull thickness changes peak pressure >5%; k-Wave vs measurement 15% pressure, 2.7 mm. Needs a big GPU for 3D.
2. **Thermal detection limits (non-invasive heat monitoring).** Batched Pennes bioheat simulations of tissue + infection; simulation-based inference of depth and size from surface readings; sensor placement. Exact textbook solutions as the answer key; baseline FEniCS on CPU. Gap: no published detection threshold for passive thermal sensing of infection. Early deep inflammation warms skin ~0.5°C then cools ~0.2°C; many depth/size combos give the same surface signal. Product space crowded (Podimetrics foot mat: 97% sensitivity, ~35 days early, company-linked).
3. **Cardiac spiral waves → ablation targets** (hand-written JAX). Thousands of ablation patterns tested at once on a 2D grid. Answer key: Niederer 2011 N-version benchmark, Fenton-Karma parameter sets. Single fast simulations already exist (Abubu.js in the browser); batched screening is new. Safest finish, lower ceiling.
4. **Hybrid bio-silicon placement.** Where scarce biological or brain-inspired compute pays off in existing systems; batched evaluation of configurations × workloads × uncertain future parameters; back-test on TPU/FPGA/tape history. Facts: Cortical Labs CL1 $35k, 25-30 W per unit vs ~0.2 mW for its neurons; 8-59 input channels; organoids live 100 days to 7 months; energy is only 7-19% of data-centre TCO; DNA storage fits cold archive only. Most novel, best sponsor fit, weak on speedup and science framing. Much of it now lives in the main idea.
5. **Olfaction (smell → disease).** ARIA runs a £65M Olfactory Perception programme (PD Claire Donoghue). Manchester's Perdita Barran: sebum swabs detect Parkinson's with 85% accuracy, up to 7 years early (experimental; no NHS launch confirmed). OpenPOM (138 odour descriptors, ROC-AUC 0.887), Pyrfume (20k odorants). Textbook disease smells as an answer key (acetone in DKA, trimethylamine, sotolone, isovaleric acid). Weak parallelism; no public disease breath data.
6. **Multi-sensor health state.** Only workable as PhysioNet 2019 sepsis: 40,336 ICU patients, two hospitals, third held back; the top five teams all scored negative on the held-back hospital. Search which non-invasive signal combinations still warn early on an unseen hospital. Modest reshaping. Wearables evidence: Duke flu 92%, rhinovirus 88% before symptoms; smartwatch malaria 7/9, ~6 days early.
7. **AV graft geometry search** (XLB lattice Boltzmann + Gaussian process loop). Strong story, interventional radiologist (Chris) for the quote; too much solver risk for the time left.
8. **CiPA virtual population.** FDA heart-cell drug-safety model across thousands of virtual patients. Easy to validate, barely a reshaping, not new.
9. **Flood uncertainty (fallback if only the three examples count).** One kernel running many scenarios with a [cell][scenario] layout (more work per memory read, shown on a roofline) + GPU multilevel Monte Carlo for flood-probability maps with error bars. Baseline: LISFLOOD-FP on all CPU cores and its GPU solver (only 2.5-4x on >1M cells). Data: Environment Agency 2D benchmarks with reference outputs. Nobody on Discord is doing flood.

Dropped earlier: hyperthermia antenna planning, proton minibeam collimator, pulse oximetry skin-tone simulation, deep brain stimulation programming, radiotherapy planning, embryo selection, colorectal anastomosis, neurochip, low-energy defibrillator, cell colony simulation. Also considered in this repo: infrared newborn brain-oxygen monitoring (possible second device).

### Benchmarking checklist (any idea)
Optimised multithreaded CPU baseline and the best existing GPU code; same precision; correctness against reference outputs; GPU timers with warm-up excluded but reported; kernel-only and end-to-end times; repeats with median and 95% intervals; problem-size and batch-size sweeps; roofline (Nsight Compute); never a single-thread or plain-NumPy baseline; verify any AI-written kernel (Sakana's 10-100x claims were withdrawn after a skipped check).

---

## 9. Sources
Event: sotaletters.substack.com/p/sota-scientific-parallelism-hackathon · luma.com/scientific-parallelism · sotaletters.substack.com/p/sota-in-manchester-ai-for-science · luma.com/concep-d6wd · ticmanchester.org/events/ai-for-science-summit
People: find-and-update.company-information.service.gov.uk/company/15818244/officers · x.com/danakarca · fossi-foundation.org/orconf/2026 · fractile.com/manifesto.html · theorg.com/org/fractile · arxiv.org/abs/2608.13331 · aria.org.uk/media/5rfpbiun/annual-report-and-accounts-2025-26.pdf · aria.org.uk/insights/introducing-our-technical-specialists · aria.org.uk/insights/stress-testing-ai-scientists · luma.com/56bp571b
Past winners: sotaletters.substack.com/p/results-from-sotas-recent-hackathons · sotaletters.substack.com/p/sota-letters-viii · sotaletters.substack.com/p/meet-our-hackathon-prizewinners
Main idea: arxiv.org/abs/2508.13181 · arxiv.org/abs/2605.29994 · arxiv.org/abs/2609.32854 · arxiv.org/abs/2406.06543 · arxiv.org/abs/2210.08277 · arxiv.org/html/2604.14550v2 · arxiv.org/pdf/2609.21157 · research.nvidia.com (GEM, RTLflow) · physionet.org/content/challenge-2017 · tinytapeout.com/faq
Other ideas: arxiv.org/abs/2202.04552 · arxiv.org/abs/2212.04405 · arxiv.org/abs/1901.02492 · gmd.copernicus.org/articles/14/3577/2021 · pubmed.ncbi.nlm.nih.gov/31939789 · arxiv.org/pdf/2012.11013 · aria.org.uk/opportunity-spaces/nature-inspired-computation/olfactory-perception · github.com/BioMachineLearning/openpom · spectrum.ieee.org/biological-computer-for-sale
