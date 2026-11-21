# Sponsors (supporters)

Four supporters: Fractile, Callosum, ARIA and Inherent Labs. None is a
biology company. Each section gives what the company builds (from
public sources), what it said in the opening talk on 21 Nov, and what
would speak to it. Lines marked **Inference** are the researcher's
reading, not a sourced fact. Full findings with every caveat are in
[data/sponsors-and-compute-ideas.json](data/sponsors-and-compute-ideas.json).

## Fractile

**What it builds.** A UK inference-chip startup, founded 2022. It
builds an accelerator for running large AI models (inference, not
training), aimed at very fast token output at long context lengths.
Its core thesis: inference is limited by moving data (model weights,
the attention cache), not by raw arithmetic. Early coverage describes
matrix maths done inside SRAM (fast on-chip memory) cells; later
podcast summaries describe a move to DRAM (larger, cheaper memory)
with SRAM-class bandwidth, claiming about 25 times the bandwidth per
chip of HBM-based parts. Raised $220M (Accel led), first commercial
chip not before 2027. Claims of "up to 100x faster, 10x cheaper" are
company statements with no independent benchmark.

Not public: whether it is analogue or digital, numeric precision,
process node, power, any measured silicon result. Do not claim any of
these.

**Opening talk** (the notes spell it "Fractal").

- Speed is the main dividend in AI; memory bandwidth is the
  bottleneck.
- Arithmetic throughput rose about a million-fold in 40 years; memory
  bandwidth only about 40-fold.
- Approach: stack DRAM on top of logic to maximise memory-to-compute
  bandwidth. Contrasted with SRAM-based Groq and Cerebras: fast but
  expensive and poor at long contexts.
- Hardware aimed at large-volume production by end of next year.
- Two Fractile staff present; Clara available on the day to help.

**What would speak to it. Inference:** a real scientific workload
shown to be memory-bandwidth-bound, measured on a roofline plot
(achieved speed against the hardware's memory and compute limits),
with bytes moved per step counted. An AI-scientist loop whose time is
dominated by token-by-token model output also fits their thesis about
long-running agents.

Sources: <https://thenextweb.com/news/fractile-220m-inference-chip>,
<https://semiconductor-digest.com/?p=27582>,
<https://www.eenewseurope.com/en/ceo-interview-walter-goodwin-fractile-ai/>,
<https://finance.biggo.com/news/9bea2d1aaa1ca2df>,
<https://fractile.com/>, <https://sacra.com/c/fractile/>

## Callosum

**What it builds.** A London software company founded by two
Cambridge-trained neuroscientists (Danyal Akarca, Jascha Achterberg).
No chips: an orchestration layer that splits an AI workflow into
subtasks and sends each to the model and chip that suits it best
("Tailored Inference" APIs). Named silicon partners include Cerebras
and Rebellions. Technology partner for ARIA's Scaling Inference Lab
cluster on mixing chip types ("Heterogeneous Orchestration",
deploying Q4 2026). Its speed and cost multipliers (for example 2x
accuracy, 7x speed, 4x lower cost) are company or investor figures
without published method. How routing decisions are made is not
public.

**Opening talk.** Not covered in the opening-talk notes.

**What would speak to it. Inference:** a scientific workload split
into stages with different needs (cheap idea proposal, heavy
reasoning, bandwidth-bound simulation), each measured on at least two
kinds of hardware or model size, and a router that beats "one big
model on one GPU" on cost per validated result. A biomedical workload
would be a new data point for them. Check on the day whether more
than one chip type is available.

Sources:
<https://fortune.com/2026/02/26/startup-callosum-cambridge-trained-neuroscientists-raises-10-million-venture-funding-orchestrate-ai-workloads-different-chips/>,
<https://www.dcvc.com/news-insights/dcvc-joins-100-million-seed-round-to-power-callosum-builder-of-a-new-orchestration-layer-for-heterogeneous-ai>,
<https://ai.engineer/orgs/callosum>, <https://callosum.com>,
<https://www.pluralplatform.com/features/why-we-invested-in-callosum>

## ARIA (Advanced Research and Invention Agency)

**What it does.** A UK funding agency, not a builder. Relevant
programmes:

- **Scaling Compute**: aims to cut the cost of AI hardware more than
  1,000-fold; nearly £100m. One pillar, "Charting the Course", funds
  simulators that predict performance, power and cost of future
  hardware and algorithm combinations.
- **Scaling Inference Lab**: an open test bed adding a new
  experimental rack about every six months, each benchmarked against
  a commercial baseline. Clusters: pipeline parallelism, mixed chip
  types (Callosum), optical switching, optical computing.
- **AI Scientists**: funding for systems that run the whole research
  process; about £500k per project for nine months.

ARIA's AI for Science Summit (26 Nov, Manchester) hosts the
first-prize demo slot.

**Opening talk.** The notes mention only a companion event in
Manchester around the same time.

**What would speak to it. Inference:** cost per unit of useful
science computation, measured at system level against a commercial
baseline, with data movement counted as well as arithmetic. A
measured workload profile plus a small cost model checked against
real runs fits Charting the Course. For AI Scientists, reporting
where the loop fails, with the compute cost of each experiment, fits
how ARIA evaluates. Frame the demo as AI for science plus compute
cost, not as a clinical device.

Sources:
<https://aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute>,
<https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/scaling-inference-lab/>,
<https://aria.org.uk/insights/scaling-compute-from-new-chips-to-working-systems>,
<https://aria.org.uk/ai-scientist>,
<https://www.resultsense.com/news/2026-01-21-aria-funds-ai-scientists-lab-experiments/>

## Inherent Labs

**What it builds.** A London AI lab (King's Cross, about a dozen
staff) founded by former Google DeepMind researchers; $50M seed. Its
AI scientist agent, Faraday, is a 27-billion-parameter open model
(Qwen) trained with reinforcement learning on "Replica": 310 tasks
from 100 papers in which the agent must reproduce a paper's figure
without seeing it. An AI judge scores design, practice, faithfulness
and resource use. The company says Faraday beats leading frontier
models at replication. Its homepage says AI can also speed up
hardware infrastructure and GPU kernels; no such work is published.

**Opening talk.**

- AI should augment human scientists, not replace them; the focus is
  the best human-model teaming.
- Text chat interfaces do not match how science is done.
- Building "living collaborator" models: proactive, curious, able to
  change their own interface; the model has the same permissions as
  human researchers and decides when to interrupt and when to act.
- Trains its own models rather than bolting tools onto frontier
  models.
- Key result: the 27B model beat frontier models at replicating ML
  papers, both general ML and AI for science. Example: it sampled
  correctly from a latent space for molecule generation, where
  frontier models only sampled from training data.
- Stays current by training a small planning model that hands coding
  to the best external coding agents.
- Hiring in post-training, infrastructure and science; the speaker
  offered to post the paper link.

**What would speak to it. Inference:** an AI-scientist loop that runs
experiments on a real simulation and scores itself on resource use
(compute per validated finding), ideally with a stage where the agent
speeds up the simulation kernel under a correctness check. A
replication-style check of a published result is in their
vocabulary.

Sources: <https://inherentlabs.ai>,
<https://inherentlabs.ai/research/training-to-replicate>,
<https://thenextweb.com/news/inherent-ai-50-million-seed-deepmind-faraday-science>,
<https://techcrunch.com/?p=3155023>,
<https://www.i-scoop.eu/faraday-inherent/>

## Event hardware

The Luma page says only that there will be GPU environments, AI
credits and mentors. It names no GPU model, count, provider or credit
amount, and no judges. Ask organisers or mentors on the day before
designing anything that needs more than one chip type or profiling
counters; keep a fallback that needs one GPU type plus model APIs.
