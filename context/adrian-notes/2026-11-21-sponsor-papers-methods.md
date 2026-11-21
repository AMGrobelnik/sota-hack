# Supporters' own methods and where our pipeline can use them

Research note, 2026-11-21. Question: after reading each hackathon supporter's own papers and essays in full, which of their named methods can the product truthfully apply and name, and how. Quotes, URLs, numbers and caveats are as in the research source.

## Summary

- Callosum: use programmable heterogeneity (Tailored Inference) and streaming parallelism (stream_map).
  - Demo sentence: Callosum calls this programmable heterogeneity: split the job, give each part its own model and its own hardware, and compare against one model on one machine; ChipIn does that for chip design, and these are our own measurements, not theirs.
- Inherent Labs: use the Replica-style replication task with an auto-generated rubric, and the scientific-integrity rule that every number is read off the final artifacts.
  - Demo sentence: For the reference model we built one replication task in the style of the Replica paper from Inherent Labs, a published result with its figure removed, a budget and a rubric that scores claim, implementation and integrity, and our agents have to reproduce it before the search starts. This is our own task and judge, not Replica and not Inherent's.
- Fractile and ARIA: use ARIA's AI Scientist definition and loop, and ARIA's static baseline with score per minute.
  - Demo sentence: We mapped our pipeline onto the AI Scientist loop that ARIA's call describes: hypothesis, experiment design, running, interpretation, report. Our experiments are in silico, not in a wet lab, and our report states which steps a human did.

## Callosum

### What was read

- https://callosum.com/blog/the-principle-of-maximum-heterogeneity: the whole post (26.02.2026). Its formulas are in the page's maths markup and came out garbled in my text conversion, so I took them from the paper itself.
- https://arxiv.org/abs/2604.07602 (full paper by Guillhem Artis, Danyal Akarca, Jascha Achterberg, all listed as Callosum; arXiv v1 8 Apr 2026, 'Working paper. First released on 26th February 2026', 88 pages). Read in full: abstract, sections 1 to 8 (model, 3.1 to 3.4 validations, 4.1 to 4.7 principles, 5.1 to 5.3 homogeneity edge cases, 6.1 to 6.3 computing, 7.1 limitations, 7.2 conclusion). Appendix read: A.1 to A.3.2 (heterogeneity-measure axioms and definition), A.4 (measure on production systems, redundancy limits), B.1 to B.5 (global optimiser, Dirac-delta argument, layer mapping, universal approximators, graph workloads), F.1 and the start of F.2. Authorship confirmed from the paper's title page.
- https://callosum.com/blog/welcome-heterogeneous-intelligence (26.02.2026), whole post.
- https://callosum.com/blog/programmable-heterogeneity ('Making Heterogeneity Programmable', 20.08.2026), whole post.
- https://callosum.com/blog/tailored-inference ('Pushing the Efficiency Frontier with Tailored Inference', 20.08.2026), whole post.
- https://callosum.com/blog/global-heterogeneous-integrator (20.08.2026), whole post.
- https://callosum.com/blog/we-are-scaling-heterogeneous-compute (26.02.2026), whole post.
- https://callosum.com/blog/seed-round, https://callosum.com/blog/introducing-callosum, https://callosum.com/product, https://callosum.com/ (home), https://callosum.com/team, https://callosum.com/terms-of-service, and the index https://callosum.com/blog (10 posts: the 7 above plus 'Seed Launch News' and 'Pre-Seed Launch News', which are lists of press headlines). The two news posts were read as titles only.
- Founder papers (found by arXiv author search; the authors are the two co-founders listed on https://callosum.com/team, Jascha Achterberg and Danyal Akarca): arXiv 2512.07602 (algorithm-hardware co-design, dual memory pathways), arXiv 2510.27434 (heterogeneous delays in low-bit networks), arXiv 2506.02813 (Mixture-of-Pathways, heterogeneous experts), arXiv 2411.00853 (dynamic execution, with Intel co-authors). Read: abstracts, introductions, the hardware and bit-budget results and the discussions; 2411.00853 in full (about 500 lines).
- Papers linked from Callosum posts but written by others, checked only for authorship via arXiv: 2507.07400 (KVFlow), 2511.02817 (Oolong), 2512.24601 (Recursive Language Models). Not by Callosum.

### Their methods

#### The Principle of Maximum Heterogeneity (what it says, what is maximised, under which constraint)

- Plain: In a simulated one-dimensional model of agents covering a demand, the best arrangement turns out to be more diverse agents, up to a limit set by how spread out the demand is. Heterogeneity is not the quantity being maximised. What is optimised is how well the agents together cover the demand, under resource limits, and heterogeneity is what the optimum looks like. The paper's own boundary is that it holds for 'distributed production systems' only.

> any distributed production system optimising for performance will converge on an increasingly heterogeneous configuration; environmental demands place an upper bound on the degree of heterogeneity required; and the communication topology of the system determines the spatial scale over which heterogeneity spreads, with this principle applying recursively across all layers of nested production systems

- URL: https://arxiv.org/abs/2604.07602 (abstract; restated in 7 Discussion: 'when a system develops towards optimal performance it needs to optimise towards heterogeneity')

- Stated conditions: Needs a demand with real spread: 'Fixed environmental demands can provide an upper bound on the need for heterogeneity' (7). For a narrow demand it predicts the opposite: 'for a unimodal Gaussian with a high peak, a homogeneous system composed of agents with same high specialisation matches the task optimally, implying no benefits of heterogeneity' (4.1). Needs agents that can communicate: 'one can force a homogeneous solution by not allowing for collaboration between agents' (5.2). Holds 'In systems that are not distributed production systems, increasing heterogeneity need not be beneficial' (7).

#### Distributed Production System model: the objective and the three constraints

- Plain: Each agent has a skill 'bump' on a circle, connected agents add their outputs, and the loss counts only the shortfall against the demand (overshoot is free). Resource scarcity divides output; communication cost and a hardware prior act as penalties. Productivity is 1/(1+loss), and it is found by gradient descent.

> The production function of S in its simplest form is: W (s, Q) = 1T (I + Q)w. ... The indicator function 1W0 >W1 (sc ) ensures we only penalise the system for operations it fails to cover, as overshooting part of the demand is acceptable while undershooting is not. ... Π(s; Q) = 1/(1 + L(s; Q)) [the PDF text layer splits this fraction; I typeset it as extracted, with 'where L is the optimisation loss'] ... L(s; Q, R) = Lm (s; W0 , R) + Lc (s; Q) + Ls (s; Q, s(2) , Q(2) )

- URL: https://arxiv.org/abs/2604.07602 (2.4, 2.6, 2.7, 2.9.3)

- Stated conditions: Demand and agents live in the same 1-D circular 'operations' space with identity mappings between layers (2.8; relaxed to order-preserving maps in B.3). The paper says its optimiser is global and 'not fully analytically solvable' (B.1). Agents are wrapped Gaussians; production is linear in agent skills (Remark 2.1).

#### Heterogeneity H and specialisation (their metric)

- Plain: A diversity count of the agents that discounts agents with similar skills, with 0 for identical agents. Specialisation is simply 1 over an agent's skill width. A population of identical agents scores 0 however large it is.

> Zij = exp(-d(mu_i, mu_j)/sqrt(sigma_i^2 + sigma_j^2)) ... H = N/(1 + (2/N) sum_{i<j} Z_ij) - 1 [typeset from the PDF text layer] ... 'This measure takes values in [0, N - 1]: lower values indicate a more homogeneous system and higher values a more heterogeneous one.' ... 'simply increasing the number of agents without introducing new skills (i.e., scaling a uniform workforce) correctly maintains zero heterogeneity' (A.4.2) ... ς(si) = 1/σi

- URL: https://arxiv.org/abs/2604.07602 (2.9.1, 2.9.2, A.4)

- Stated conditions: Needs each agent described by a mean and width in the shared skill space. It is a Hill number of order 2 with Leinster-Cobbold similarity (A.3).

#### Heterogeneous scaling law (log-logistic in the number of agents; workload predicts the plateau)

- Plain: As agents are added, the optimal heterogeneity rises quickly and then flattens. The plateau is best predicted by how heterogeneous the demand itself is.

> the optimal heterogeneity H∗ and optimal specialisation scale with the number of agents as a log-logistic function: H∗(x) = H∞/(1 + (x/a)^−γ) ... the intrinsic heterogeneity of the workload distribution is the single feature most predictive of the system-level heterogeneity that emerges from optimisation

- URL: https://arxiv.org/abs/2604.07602 (4.1, 4.2; r = 0.90 for the best predictor across 8 workloads, Figure 21)

- Stated conditions: Fitted on 8 (then 16) synthetic Gaussian-mixture workloads. 'the scaling of heterogeneity with production system size depends on the workload' and the fit is 'less well approximated' for peaks of unequal size (4.1). The 'transition regime' constants a and gamma are left open: 'investigating these effects is beyond the scope of this manuscript' (4.2).

#### Efficiency under scarce resources (heterogeneous beats homogeneous, homogeneous catches up with enough resource)

- Plain: With a fixed budget, the mixed system reaches near-best coverage with fewer agents. A uniform system needs more resource to match it, and at unlimited resource both reach the same ceiling. The numbers are in arbitrary model units.

> the heterogeneous system reaches near-optimal productivity already at N = 4 and remains flat thereafter, while the homogeneous system climbs steadily but does not match the heterogeneous curve until N ≈ 11 ... in the limit with infinite resources both systems are as performant, but that for most resource-constrained systems, heterogeneous systems will be more performant

- URL: https://arxiv.org/abs/2604.07602 (6.2, Figure 32; also 4.4, where heterogeneity-performance correlation r = 0.976, rising to 0.997 under scarcity)

- Stated conditions: 'Of course the units representing system size in Figure 32 are arbitrary and do not map onto actual real-life units.' The summary figure (Figure 33) 'shows a schematic and does not show an actual analysis based on model simulations.' Blog version: 'However, when resources are limited, heterogeneous hardware delivers better performance.' (https://callosum.com/blog/the-principle-of-maximum-heterogeneity)

#### Heterogeneity as insurance (robustness to a shifting demand)

- Plain: When the demand drifts or a shock arrives, the mixed system keeps a higher floor and lower variance, at the price of lower peak performance when the demand matches the uniform system exactly.

> heterogeneity acts as an insurance policy whose premium, a modest reduction in peak performance when conditions are not perfectly matched, buys substantially lower variance and a higher floor when conditions inevitably shift ... the homogeneous system suffers severe output collapses when tasks shift away from its narrow competence

- URL: https://arxiv.org/abs/2604.07602 (4.5, F.2; tested on 48 tasks x 3 regimes with t-tests and Wilcoxon tests; when the task was centred exactly on the homogeneous agents, the homogeneous system had '4x higher mean production under Brownian motion (p = 0.04)')

- Stated conditions: Two-agent systems (N = 2) with resource level 4; synthetic tasks. Peak-matched homogeneous designs win on mean when the task matches them.

#### Radius of collaboration and locality of heterogeneity

- Plain: The diversity a system can express is capped by the largest group that can talk to each other. Costly communication makes tightly linked agents alike and weakly linked ones complementary, with a sharp transition.

> the heterogeneity of the whole system is bounded above by the heterogeneity achievable within its largest connected component ... Hence, communication costs induce a locality of heterogeneity

- URL: https://arxiv.org/abs/2604.07602 (4.3.1, 4.3.2; 8 agents, 20 seeds; phase-transition-like at communication weight around 5e-4)

- Stated conditions: The model in its simplest form has interactions acting only at connected-component level: 'This interaction will be made deeper for the next iteration of the model' (footnote 1, 2.6).

#### Recursive property (heterogeneity propagates through nested layers: workload, algorithm, hardware)

- Plain: If the top layer's best solution is a broad mix, that broad output is the demand for the layer below, so the layer below is also mixed, all the way down to hardware. It breaks only if a layer collapses the workload to a single value.

> Heterogeneity at the top therefore induces heterogeneity all the way down. ... Only a complete collapse of the workload to a near-uniform or Dirac-delta function at some layer would break the chain ... There is no point where we can say 'heterogeneity has been achieved on the top layer, we can now build an ideal system homogeneously below it'. (blog)

- URL: https://arxiv.org/abs/2604.07602 (4.6; B.3) and https://callosum.com/blog/the-principle-of-maximum-heterogeneity

- Stated conditions: Needs inter-layer maps that are 'order-preserving on the region of skill space where the inter-agent variance lies' (4.6, B.3). The argument is by reasoning plus simulation, not a theorem; the blog says 'The full paper addresses the technical objections we anticipate'.

#### Hardware-lottery experiment: heterogeneous hardware aligned to the workload

- Plain: Pull all six agents toward one hardware operating point and coverage collapses (perf about 0.69). Free agents reach about 0.99. Hardware spread to match the workload recovers about 0.94, and slightly misaligned hardware gets about 0.81. Design rule: spread the hardware to mirror the structure of the workload one level up.

> the most effective strategy to mitigate the hardware lottery is to introduce heterogeneous components whose specialisation mirrors the structure of the workload at the level above

- URL: https://arxiv.org/abs/2604.07602 (6.1, Figures 30 and 31; N = 6 agents)

- Stated conditions: Stylised: 'hardware' is a prior pulling each agent's skill centre; performance is 1/(1+L) in model units, not seconds or gates.

#### Rule for assigning sub-tasks to models or hardware: what exists and what does not

- Plain: The paper gives no assignment algorithm; it assumes the assignment is already optimal and argues the result survives random assignment. The operational rules are only in Callosum's product posts: break the task into typed blocks, give each the smallest model that works, search over model-by-silicon pairings, and learn a router.

> An implicit assumption of the model is that task assignment is optimal: each agent i is allocated the subworkload it is best placed to cover (paper 5.3). Product posts: 'decompose the workflow, match each step to the smallest model that can solve it' (Welcome post); 'What was previously a single model choice becomes a search space over the shape of the workflow graph, the model at each node, and the silicon each one runs on. Instead of returning one solution, searching the space yields a family of optimal configurations.' (Tailored Inference post)

- URL: https://arxiv.org/abs/2604.07602 (5.3); https://callosum.com/blog/welcome-heterogeneous-intelligence; https://callosum.com/blog/tailored-inference

- Stated conditions: Their search method, scoring and code are not published ('not found' on every page read). Paper: 'We do not claim that the optimal configuration under random assignment is identical to that under perfect assignment' (5.3).

#### Heterogeneous recursion (models and silicon assigned per level of a recursive language model)

- Plain: A planner model sets the plan and sub-models on other chips do expansion, retrieval and verification. They report that the way the recursion is partitioned matters more than the strength of any one model.

> the way you partition the recursion: which model handles which level, on which chip, and at which point in the reasoning chain, matters more than the raw capability of any individual component. ... Cerebras GPT-OSS-120B delivers the same accuracy at 5x the speed and 7x lower cost than GPT-5. ... No single configuration dominates across every objective.

- URL: https://callosum.com/blog/welcome-heterogeneous-intelligence (Deep Context section; heading '12x cheaper, 5.5x faster'; OOLONG benchmark)

- Stated conditions: Self-reported by Callosum on one benchmark (OOLONG) against 'GPT-5 as a recursive language model'; Coworker AI run on vLLM GitHub logs: '2.1x cheaper with a +13 point quality improvement' at 30k tokens and '1.8x cheaper and +13.5 points higher quality' at 200k, versus single-call Claude Opus 4.5. No variance or code found in the text; the charts were not viewed.

#### Programmable heterogeneity: blocks, program search, placement

- Plain: Tasks are written as programs of typed, pre-verified blocks (split, filter, rank, reflect...). Most blocks can be ordinary code, some call a model, and each can be placed on a different chip. Searching programs and placements gives a cost-speed-quality frontier that single frontier agents sit well off.

> Heterogeneous programs are 3.5× cheaper, 3.7× faster and 16.9 points of F1 score higher than the closest frontier agent ... Here, we hold Program A fixed (the same blocks in the same order) but vary the model and silicon used for each block. ... not every block is a model. Some, if not most, can be deterministic functions.

- URL: https://callosum.com/blog/programmable-heterogeneity

- Stated conditions: Agentic code-search task, nearest baseline named as 'GPT-5.6 Luna'; 'How much less depends on which baseline you take.' Cerebras-only configuration 'prioritises speed', GPU-only 'prioritises cost', and the best balance is a mix. 'We searched over model, program and silicon – only silicon shown here.'

#### Streaming parallelism instead of bulk synchronous (stream_map)

- Plain: If a program is written as dependent blocks, later calls can start as soon as any earlier output arrives instead of waiting for all of them. They measured the saving on one composite.

> To change from bulk synchronous parallelism (BSP) to streaming parallelism is to simply swap the map() block to stream_map() in the program. ... This further reduces the average execution time 1.58× from 1.9s to 1.2s on Cerebras

- URL: https://callosum.com/blog/programmable-heterogeneity

- Stated conditions: One composite ('evidence_pass()') on Cerebras; needs the work expressed as a dependency graph so 'nothing waits on anything it does not depend on'.

#### Learned router over models and hardware

- Plain: A trained transformer picks, per request and per accuracy-cost preference, which model and hardware to use. At equal accuracy it is faster and cheaper than the best fixed configuration. They link the effect back to the principle.

> at equivalent accuracy to the best fixed configuration, the router is 1.8× faster, amounting to a total 10.1× speed-up over the same model run on frontier GPUs. At maximum accuracy, it improves performance by 1.8 percentage points while remaining 5.9× faster than the GPU baseline. ... The answer reaches back to our paper on the Principle of Maximum Heterogeneity

- URL: https://callosum.com/blog/programmable-heterogeneity (router section; held-out MATH, GSM8K, E2H-AMC, AIME)

- Stated conditions: 'Latencies are computed from Artificial Analysis data' (figure caption), so the GPU comparison uses third-party latency figures. Needs many models available and a trained router; their stated inputs include cost, cache state, context fit, data locality.

#### Heterogeneous cognitive offloading (small sub-agent takes the retrieval work)

- Plain: The main agent hands document search to a smaller sub-agent and sees only the passages that matter, so its context stays small. This also lets the main agent fit a fast chip.

> Simply replacing default search tools with one sub-agent improves pass rate of GPT5.5 from 44.6% to 49.5% while cutting the main agent's cumulative context from 1,193k to 428k tokens per conversation. ... Moving the main agent across as well can accelerate the whole task from 280.2s to 108s, while reducing the cost by 14.1%. ... Callosum's retriever subsystem offloads context from the main agent to a much smaller subagent (GPT-OSS-120B)

- URL: https://callosum.com/blog/programmable-heterogeneity (last section, tau-cubed banking benchmark)

- Stated conditions: Needs a task that separates cleanly into 'retrieval reasoning' (iterative, stateless) and 'task reasoning': 'Separating these two parts enables heterogeneity: two kinds of work, two kinds of compute.' Measured on 56% retrieval-related calls in the leaderboard's GPT-5.5 trajectories.

#### Topology-aware cache eviction and 'many shots made free' (ensemble inference on-chip)

- Plain: Two systems results: use the workflow graph to evict the cache entry furthest from future use (an application of Belady's rule), and move JSON-grammar masking on-chip so that many parallel candidates cost almost no extra latency, letting a 1B model match an 8B one.

> up to 2.4x in prefill-dominated regimes ... The model does not need to be smarter. It needs more shots, and the infrastructure needs to make them free. ... latency stays nearly constant across candidate counts thanks to parallel execution

- URL: https://callosum.com/blog/welcome-heterogeneous-intelligence (Cache-Intensive and Tool Calling sections; Inferentia2, 1,767x faster grammar masking at batch 64; 1B model with 8 candidates 42.27%, +11 points over greedy)

- Stated conditions: Speedup applies 'whenever there is a cache deficit'. Tool-calling result is on AWS Inferentia2 with custom kernels. Ensemble gain assumes candidates answer the same query and a selection rule picks one.

#### Tailored Inference (product): continuous search for the Pareto frontier of cost and speed

- Plain: Their only product. They decompose a customer's workload, assign each node its own model and chip, and keep the configuration on the cost-speed frontier as models and chips change. Customer case studies quote 7x to 77x gains.

> We continuously profile the space of models, hardware, and configurations, to ensure your system is on the Pareto frontier and stays there. ... We disaggregate these systems, splitting workflows across models and hardware, exposing otherwise inaccessible optimisation surfaces.

- URL: https://callosum.com/product ; case studies at https://callosum.com/blog/tailored-inference (HelmGuard '$0.08 per 1,000 traces analysed, 77x cheaper than the closed-source monolithic judge'; Round Treasury 'mean extraction time fell from 15.9s to 2.1s per document'; Deliverance 64s to 6.5s)

- Stated conditions: Inference workloads only; customer-quoted; docs sit behind sign-in (not accessed). The HelmGuard result is stated 'at frontier-model detection quality'.

#### Algorithm-hardware co-design with post-layout hardware results (founders' paper, not the company's product)

- Plain: A spiking-network design whose algorithm was shaped by hardware cost, plus a digital near-memory accelerator. Post-layout 22nm simulation shows over 4x throughput and over 5x energy efficiency versus the compared designs. The hardware design is open-sourced.

> Imposing hardware considerations at the algorithmic level results in a network architecture with a temporal memory that is explicit and low-rank. ... Post-layout simulations of the proposed hardware architecture in an advanced 22FDX technology demonstrate more than 4× higher throughput and over 5× better energy efficiency compared with SOTA designs.

- URL: https://arxiv.org/abs/2512.07602 (abstract, 1 Introduction, 2.4, 3 Discussion; Sun, Su, Achterberg, Indiveri, Goodman, Akarca)

- Stated conditions: Spiking networks for event-driven sensing, 'primarily designed for edge computing'; compared against Loihi 2, ReckOn, ElfCore, DenRAM. Simulation after layout, not fabricated silicon (not found in the text read).

#### Bit-budget landscape and memory-accuracy Pareto frontier (founders' paper)

- Plain: They sweep weight bits and delay bits to map accuracy against memory, mark the frontier, and show that with learned delays the same accuracy needs about 20 times less parameter memory.

> Notably, this directly informs neuromorphic hardware deployment because processors operate under strict “bit-budgets” that constrain parameter allocation ... while reducing parameter memory by 20×, 20×, 19× on SHD, SSC, NTIDIGITS respectively

- URL: https://arxiv.org/abs/2510.27434 (2.1, Figure 2; Sun, Achterberg, Su, Goodman, Akarca)

- Stated conditions: Feedforward spiking networks on auditory and gesture benchmarks; ternary weights (1.58 bit) and learned axonal delays. 'these datasets remain limited in capturing the full complexity of real-world temporal dynamics' (3 Discussion).

#### Routing cost on complexity (Mixture-of-Pathways) and dynamic execution (founders' papers)

- Plain: Two smaller ideas from the founders. A loss term that makes it costly to use larger experts, scaled by task performance, makes a small model route consistently. Separately, 'dynamic execution' does just enough work for the difficulty of each input (early exit, speculative decoding, routing).

> a routing cost that penalizes the model for using larger experts ... Early Exit is a category of techniques based on this simple principle of doing 'enough work' given the difficulty of the input.

- URL: https://arxiv.org/abs/2506.02813 (Cook, Akarca, Costa, Achterberg; NeurIPS 2025); https://arxiv.org/abs/2411.00853 (Barad, Achterberg, Chou, Yu; Intel co-authors, written before Callosum existed)

- Stated conditions: Mixture-of-Pathways: three tiny experts on 82 cognitive tasks, 'Our small-scale simulations show how it may be possible'; scaling to larger networks untested ('we would need to train larger models on more difficult tasks'). Dynamic execution paper is a review plus Intel-platform results, not Callosum work.

#### Funding and standing claims relevant to the notes' gaps

- Plain: Callosum's own pages confirm an ARIA grant and a $100M seed. The notes only had this from the press.

> a $2.9 million ARIA grant to pioneer R&D on the first co-located heterogeneous compute cluster for multi-agent intelligence (blog 26.02.2026); 'Today we announce our $100M seed round ... The round is led by Atomico' (20.08.2026)

- URL: https://callosum.com/blog/we-are-scaling-heterogeneous-compute ; https://callosum.com/blog/seed-round

- Stated conditions: Their 'We have proven formally that systems composed of diverse models and compute substrates outperform any homogeneous system' is a stronger sentence than the paper supports (see misuses).

### Where it applies in our pipeline

#### 1. Programmable heterogeneity / Tailored Inference: split the job, give each part its own model and hardware, and report cost and time against the single-model, single-machine monolith

- Where: The whole pipeline, as one stage-by-resource table: (2) language agents (Claude or OpenRouter model for design, gpt-oss-120b for summaries); (3) GPU batch fine-tuning; (4) Yosys synthesis on CPU cores and layouts in containers; (5) bit-for-bit and formal verification.

- Already exists: The assignment is already in the product (each stage on a different model or hardware), and three single numbers are measured: 256 candidates per batch at 1,626 per minute, 2,330 gates, 3,880 of 3,880 windows. What is missing is a measured monolith baseline, which is the part Callosum's own posts always include.

- To build, and the number to report: A benchmark script that runs each stage on its chosen resource and on a monolith alternative with the same seed and the same candidates, and writes one JSON row per stage: GPU batch versus the same candidates trained one at a time or on CPU only; synthesis on 1 core versus all cores/containers; summaries by gpt-oss-120b versus Claude, with an automated faithfulness check (every number in the summary appears in the run log); design proposals by Claude versus Inkling 2 Mini (cost, time, valid-design rate). Dashboard: a table 'stage, ran on, time, monolith alternative, time', with each cell labelled 'measured' or 'extrapolated from per-stage measurements'. Headline number: end-to-end wall-clock (and dollars only if prices are stated) of the pipeline as built versus every stage on one resource. Report the run count and show spread.

- Sentence for the demo: Callosum calls this programmable heterogeneity: split the job, give each part its own model and its own hardware, and compare against one model on one machine; ChipIn does that for chip design, and these are our own measurements, not theirs.

- Why their people would accept it: It is the exact structure of their Tailored Inference case studies (per-node model and silicon, compared with a monolithic baseline), and you report your own baseline rather than borrowing their 3.7x or 77x.

#### 2. Heterogeneous cognitive offloading: a small open model reads the logs and the main agent sees only the summary

- Where: Step (2): gpt-oss-120b writes run summaries that the design agent (Claude or an OpenRouter model) uses when proposing the next round of designs.

- Already exists: Partly. gpt-oss-120b already writes the summaries (stated in the brief). Not confirmed from the notes: that the design agent reads the summary instead of raw logs, and nothing is measured yet; check this before saying anything.

- To build, and the number to report: Log input tokens and dollars on every design-agent call (the API usage field) in two arms over the same rounds: raw logs in context versus the gpt-oss summary. Add the faithfulness check from application 1 and confirm the final design quality is the same. Dashboard: two bars, 'design-agent input tokens per round', raw versus summary. Number: the ratio, with run count.

- Sentence for the demo: This is the split Callosum describes for long-context work: a small open model, GPT-OSS-120B in their case too, reads the bulky logs and the main agent only sees what matters; here is our measured token and cost difference.

- Why their people would accept it: Their own measured example uses GPT-OSS-120B as the offloaded sub-agent and reports the main agent's context falling from 1,193k to 428k tokens, so the same pattern with your own tokens counted is recognisable and modest.

#### 3. Streaming instead of bulk-synchronous execution: start the next stage as soon as its inputs exist

- Where: Between steps (3), (4) and (5): while the GPU fine-tunes round r+1, the CPU cores synthesise, lay out and verify the top candidates of round r.

- Already exists: Layouts already run in parallel in containers. Not known from the notes: whether rounds overlap across GPU and CPU or wait on each other.

- To build, and the number to report: An orchestrator change (a queue or asyncio task) that launches synthesis and verification of the top-K as soon as a round ends while the GPU begins the next round. Dashboard: a lane timeline (LLM, GPU, CPU) from timestamps already logged. Number: wall-clock for N rounds with a barrier versus overlapped, same seed, same hardware, repeated runs. Only describe it this way if it is built and timed.

- Sentence for the demo: Callosum's term for not waiting for every task before starting the next is streaming parallelism; ChipIn overlaps its GPU and CPU stages for the same reason, and here is the timeline and the time saved.

- Why their people would accept it: It is their bulk-synchronous-to-streaming point (1.9s to 1.2s on one composite), and it is the one place where having different hardware for different stages gives a free, directly measurable win.

#### 4. Learnable algorithm-hardware co-design, shown as an accuracy-versus-gates frontier (their 'bit-budget' idea)

- Where: Steps (3) to (6): the design search, the compile to gates, and the report on the smallest chip that meets the clinician bar.

- Already exists: Partly. The pipeline returns the smallest chip that meets the bar and measured one point, 2,330 gates at 3,880 of 3,880. Whether gate counts feed back into later design rounds is not stated in the brief.

- To build, and the number to report: Synthesise the top 8 to 16 candidates of the final round in parallel on CPU (Yosys), and plot accuracy against gate count with the clinician bar drawn and the chosen chip marked. If weight bit-width is not already a design choice, add it as a candidate parameter (for example 2, 4 and 8 bits) so the frontier has a bit axis. Baseline: the reference model compiled with the same Yosys script at the same bar. Number: gates of the chosen chip over gates of the reference at equal accuracy, both measured.

- Sentence for the demo: The founders of Callosum call choosing a model with its hardware cost in the loop algorithm-hardware co-design; ChipIn does it at the level of gates and shows the whole accuracy-versus-gates frontier rather than a single design.

- Why their people would accept it: Their paper calls for 'learnable algorithm-hardware co-design ... at scale', and their founders' own hardware work reports a bit-budget frontier and post-layout numbers, so a measured frontier with a stated baseline reads as the same practice.

#### 5. Many shots made nearly free: candidates in one GPU batch

- Where: Step (3), the 256 candidates per batch at 1,626 per minute.

- Already exists: Yes, and measured as throughput. The missing piece is the credible baseline (the same candidates trained one at a time) and how time grows with batch size.

- To build, and the number to report: A batch-size sweep (1, 4, 16, 64, 256) on the same model and data: time per batch, candidates per minute, and speedup against sequential training. Dashboard: one chart of time per batch against number of candidates. Number: candidates per minute at 256 over at 1, measured, with run count.

- Sentence for the demo: Callosum's line is that the model does not need to be smarter, it needs more shots and the infrastructure has to make them nearly free; ChipIn's version is hundreds of small designs per GPU batch, and here is the measured speedup over training them one at a time.

- Why their people would accept it: It echoes their result that latency stays nearly constant across candidate counts, and you state the difference: your shots are different designs being searched, not votes on one answer.

#### 6. The Principle of Maximum Heterogeneity as the stated reason, with no number attached

- Where: One explanatory slide or sentence about why the pipeline is mixed: its work spans language reasoning, batched matrix maths, logic synthesis, geometry and equivalence checking.

- Already exists: Yes, as a description. It is a theory, so there is nothing to implement and nothing to measure for it.

- To build, and the number to report: Nothing for the number. Use the stage-by-resource table from application 1 as the evidence. Do not compute their heterogeneity score H (it needs agents described by a skill mean and width on one circle; no honest mapping exists for ChipIn's stages).

- Sentence for the demo: Callosum's principle says that when the work has a wide spread of operations the best system is a mix, repeated at every layer down to hardware; our pipeline is a mix for that reason, and our evidence is our own measurement, not a test of their model.

- Why their people would accept it: It keeps their theory and your measurement separate and does not claim their model predicted your result.

### Do not

- Calling the final chip 'maximum heterogeneity' or an instance of the principle. The paper predicts the opposite for a narrow workload: 'for a unimodal Gaussian with a high peak, a homogeneous system composed of agents with same high specialisation matches the task optimally, implying no benefits of heterogeneity' (4.1), and for a single fixed function 'This is an edge case that does break the optimisation of the model, so our model does not make specific prediction for such cases' (5.1). A single-purpose chip is a specialist; heterogeneity in their sense is a property of a population of different agents.

- Counting 256 near-identical candidates in one GPU batch as heterogeneity. By their own metric 'simply increasing the number of agents without introducing new skills (i.e., scaling a uniform workforce) correctly maintains zero heterogeneity' (A.4.2). The heterogeneity in ChipIn is across stages (different models and hardware), not inside the batch.

- Saying ChipIn 'routes' or 'orchestrates' like Callosum. Their router is a trained transformer choosing per request (https://callosum.com/blog/programmable-heterogeneity), and their assignment is searched. ChipIn's stage-to-hardware assignment is fixed by hand unless a search is built. Also the paper only assumes assignment is optimal: 'An implicit assumption of the model is that task assignment is optimal' (5.3); it provides no assignment algorithm.

- Quoting their headline numbers (3.5x cheaper, 3.7x faster, 10.1x, 12x, 77x, 2.4x, 1,767x) as results or expectations for ChipIn. They are self-reported on their own pages, on language-model workloads against baselines they chose ('How much less depends on which baseline you take'), with no code or error bars found in the text.

- Repeating 'We have proven formally that systems composed of diverse models and compute substrates outperform any homogeneous system' (https://callosum.com/blog/we-are-scaling-heterogeneous-compute). The paper's evidence is simulation in a one-dimensional model: the summary figure 'shows a schematic and does not show an actual analysis based on model simulations' (Figure 33) and 'the units representing system size in Figure 32 are arbitrary and do not map onto actual real-life units' (6.2). Their paper also says homogeneous systems catch up with enough resource.

- Saying heterogeneous hardware 'always wins' for ChipIn. The paper's own robustness test found the opposite on a matched task: 'the homogeneous system achieves a 4× higher mean production under Brownian motion (p = 0.04)' when the task is centred on it (4.5). The honest version is the insurance trade: peak versus floor.

- Using Callosum's brain results as support for ChipIn. The brain match (multiple-demand network, retina filters) validates their model of agents covering a demand, not a medical chip. The founders' spiking-network papers (dual memory pathways, delays) are not about EEG chips or gate-level netlists; citing their 4x, 5x or 20x numbers for ChipIn would be wrong.

- Implying Callosum designs chips, does synthesis or training, or endorses the project. Their product is inference only (https://callosum.com/product), they work with silicon partners, and the founders' hardware paper is an academic co-design with ETH Zurich and Imperial College. The notes' do-not-claim list still holds; the terms state 'The trademarks and logos displayed on this Site and any affiliated sites are, unless indicated, the property of Callosum', so plain text only.

- Reporting their heterogeneity score H for ChipIn. It is defined on agents with a skill mean and width on a shared circle (2.9.2); no such description of ChipIn's stages exists, so any value would be invented.

- Reading the 'Hardware Lottery' argument as saying ChipIn is the answer. The paper's remedy is to add heterogeneous accelerators that mirror the workload and integrate new chips into a stack (6.1; blog: 'getting a flywheel going that spurs new kinds of chip architecture'); it does not say to bake one model into gates. ChipIn can say it lowers the cost of making a task-specific chip, not that Callosum's theory predicts it.

- Claiming the 3-minute demo shows 'routing across accelerators' or 'co-evolution of chips and intelligence'. The latter is Callosum's own phrase for their infrastructure ('We co-evolve chips and intelligence together'); using it for ChipIn claims their work.

### Their own open problems

- Workloads as graphs: 'Our model treats workloads as flat distributions over tasks, but in practice workloads have internal dependency structure: operations must often be executed in a specific order, forming graphs rather than independent draws.' (7.1). ChipIn is a dependency graph of stages (spec, train, synthesise, verify), so a measured per-stage timeline is a worked example. It is not a test of their model; B.5 only argues the principle should still hold.

- Parallelism hides work: 'in real computing systems some operations can be hidden through parallelisation, effectively reducing their weight in the distribution; this is consequential primarily in peak-heavy workload distributions' (7.1). ChipIn's one-batch training of hundreds of candidates is a concrete case of an operation made cheap by parallelism.

- Breaking the hardware lottery needs fast iteration on new hardware: 'New hardware and algorithms need to be able to find their use cases and niches of utility in complex workflows during quick iteration cycles' and 'getting a flywheel going that spurs new kinds of chip architecture' (https://callosum.com/blog/the-principle-of-maximum-heterogeneity). ChipIn can speak to the cost and time of producing a task-specific chip design, with its measured numbers.

- Learnable co-design at scale: 'move to a world where learnable algorithm-hardware co-design is possible at scale' (6.3). ChipIn is a small, automated instance for one task; say 'small instance', not 'scale'.

- Robustness to change is an insurance premium: 'heterogeneity acts as an insurance policy whose premium, a modest reduction in peak performance when conditions are not perfectly matched, buys substantially lower variance and a higher floor when conditions inevitably shift' (4.5). A chip with weights wired in has no way to adapt; ChipIn can report accuracy on held-out recordings or subjects as its own check of that floor, as it cannot rely on the theory for it.

- Their 'orchestration problem': the paper lists it among 'the technical objections we anticipate' (blog) and answers only that random assignment still favours heterogeneity (5.3). In the product post: 'What remains is the question of which of them should serve a given request, and that is what we learn next.' ChipIn's fixed hand-chosen assignment is an honest simple baseline for that question.

- Missing agent differences: 'our model does not currently account for resource depletion at the lower level, nor does it handle cases where agents differ substantially in overall skill level rather than in the shape of their skill distribution' and it 'does not straightforwardly account for cases of strong within-feature homogeneity' (7.1). A single fixed-function chip is the within-feature-homogeneous case.

- Founder-paper limits: spiking benchmarks 'remain limited in capturing the full complexity of real-world temporal dynamics' (2510.27434, 3 Discussion); the dual-memory hardware is 'primarily designed for edge computing' and 'Deploying it on these systems would enable broader evaluation' (2512.07602, 3). An edge medical-sensing chip is the kind of embodied, resource-limited target they say lacks benchmarks.

### Not read

- Paper appendix not read (arXiv 2604.07602, 88 pages): the rest of A.3.2 (the proof of the heterogeneity-measure limits), A.3.3, A.3.4; Appendix C (technical verifications of the optimiser, wrapped-Gaussian properties); Appendix D (simulation parameters, workload metrics); Appendix E (network effects); the remainder of F.2 after the unimodal-catalogue paragraph; the reference list. The main text and Appendices A.1 to A.3.2, A.4, B and F.1 were read.

- Figures and charts on every page, and the demo video in the Welcome post, were not viewed; I used captions and body text only. Error bars or confidence intervals for the blog results were therefore not checked; none were found in the text. Callosum's blog results are all self-reported and I found no code, data or public repository.

- Founder papers read only in part: the algorithm results (2.1 to 2.3) and Methods of 2512.07602; Results 2.2 to the end of 2.3 and Methods of 2510.27434; Results 4.2 onward and appendices of 2506.02813. 2411.00853 was read in full. Other founder papers (the 2023 primer arXiv 2303.13651, the spatially-embedded RNN papers, the belief-propagation and cognitive-map papers) were identified from titles and not read; they are not about heterogeneous compute for chips.

- docs.callosum.com (API documentation) is behind sign-in and was not accessed, so no API shape, pricing, model list or hackathon offer is confirmed (the notes' open question about OpenAI-compatible access is still open). No Callosum page on the hackathon itself or the Saturday talk was found or read. No press or brand-usage page was found; the terms say only that trademarks and logos are Callosum's property, so permission for logo use still needs press@callosum.com (listed on their pages).

- The 20.08.2026 press-headline posts (Bloomberg, Sifted, DCVC, Atomico and others) were read as titles only. The 3.7x figure the notes attribute to a news outlet is on Callosum's own Welcome page as 'up to 3.7× cheaper (~$0.22 vs ~$0.83 per task) and 3× faster' for a GPT-5.2 plus Qwen3-VL-8B configuration on VisualWebArena shopping tasks.

- Whether ChipIn's design agent actually reads gpt-oss-120b summaries rather than raw logs, whether rounds overlap across GPU and CPU, whether gate count feeds back into later design rounds, and whether weight bit-width is already a design choice: not stated in the brief or the notes, so applications 2, 3 and 4 depend on checking the code first.

- The arXiv API listed 12 Akarca and Achterberg papers; the author search can miss some. The Callosum authorship of the Principle paper is confirmed on its title page (affiliation 'Callosum, London'); the two Callosum co-founders are named on https://callosum.com/team.

## Inherent Labs

### What was read

- Paper, arXiv:2608.13331 'Training AI Scientists to Replicate Research' (HTML version https://arxiv.org/html/2608.13331, v1, 13/14 Aug 2026), read in full from the raw HTML (not through a summariser): title, abstract, Sections 1-5, Ethics statement, Acknowledgements, Appendix A (A.1, A.2), B (captions), C (captions), D (D.1, D.2, Table D.1), E, F (F.1, F.2, F.3, Tables F.1 to F.4 mostly), G (G.1 Faraday system prompt, G.2, G.3 task prompt, G.4 human rater prompt, G.5 optimised Codex prompt, G.6 three complete example rubrics: Zucchet et al. Fig 5, Friedman et al. Fig 5, Gers et al. Fig 4), H (infrastructure), and all figure and table captions.
- Research page https://inherentlabs.ai/research/training-to-replicate (14 August 2026): read in full from the raw HTML.
- Homepage https://inherentlabs.ai/ : read in full, including the manifesto 'Living within the Experiment' (Sections I to III, authors Collins, Hughes, Kirsch, Aleksiev) and its list of open questions. This is the organisation's only other essay.
- Research index https://inherentlabs.ai/research/ : read; it lists exactly one item (the Replica paper).
- Earlier team notes read first: context/adrian-notes/2026-11-21-sponsor-wording-check.md in full, and the Inherent-related lines of 2026-11-21-sponsor-integrations.md (via grep for inherent/replica/2608).
- Downloaded files and the temporary scripts were deleted (absolute literal paths); nothing was signed up for, logged into or submitted; no project details were sent to any site. Two WebFetch summaries were used only to locate the text; no claim below relies on them.

### Their methods

#### Replica (task space) and the Replica task format

- Plain: Replica is a set of automatically generated tasks, each asking an agent to reproduce one results figure from a published paper whose figure has been removed. A task is a caption, the hidden original figure (the 'gold plot') and the redacted paper, plus a fixed time and compute budget.

> A task is a triple of caption, extracted figure (“gold plot”), and paper with figure redacted.  ... Each task requires an agent to replicate one results figure from a paper, given the original paper with the figure redacted, a 60-minute time limit, and a single one-seventh MIG slice of an H200 GPU.

- URL: https://arxiv.org/html/2608.13331 , Section 3.1 (Task space); Figure 1 caption; task prompt in Appendix G.3

- Stated conditions: 242 training tasks (ML papers 1990 to 2026) and 68 test tasks (AI-for-science papers 2012 to 2026), 310 tasks from 100 well-known papers, 1 to 13 tasks per paper, median 2. Built by three Gemini 2.5 Pro vision stages ('A scan finds every main-text results plot and its caption, a localisation stage draws its bounding box inside an LLM-verifier repair loop, and the figure is irreversibly redacted from the PDF') and 'We inspect every task by hand and filter out any that are of low quality'. The agent works in a container with internet, git, and must write plot.png and writeup.md. Task prompt rules (G.3): 'You must NOT look up or download the original paper PDF from the internet'; 'You must NOT simply guess or fabricate the plot'; 'You will be assessed on the whole commit history, not just the final plot'. Scale-down is allowed: 'Where a paper’s experiment cannot be completed within the given time budget, the prompt asks for the most faithful scaled-down version of the underlying experiment.' The agent is told 'you will be penalized for unnecessarily scaling down' when full scale fits.

#### Per-task, auto-generated rubric (how the rubric is constructed)

- Plain: For each task a language model writes a task-specific scoring guide from the paper and caption, without seeing the original figure, so the rubric tests the paper's claim and not the figure's pixels. The rubric is hidden from the agent being trained and rewards a faithful scaled-down experiment.

> Starting from a short, hand-designed meta-prompt, we use Claude Opus 4.7 to auto-generate task-specific rubrics. We hide the “gold plot” from the rubric generator so that the rubric captures the claims of the paper without over-indexing on figure details such as axis ranges, formatting, and exact numerical values. The judge rubric is also hidden from the model during training, encouraging the model to produce broadly effective replications rather than game the rubric criteria.

- URL: https://arxiv.org/html/2608.13331 , Section 3.2 (Judge rubric generation); example rubrics in Appendix G.6

- Stated conditions: Five dimensions, as listed in 3.2: 'The judge rubric covers five dimensions: (1) how closely the replicated figure visually matches the paper’s, (2) how well the replication supports the paper’s scientific claim, (3) whether the underlying experiment actually implements and tests what the paper describes, (4) whether the agent makes good use of the compute budget, and (5) whether the agent acted with scientific integrity, adhering to its instructions and not cheating.' The three example rubrics in G.6 are each: a one-paragraph statement of what the figure argues, then four headed sections (1. Visual fidelity, 2. Claim reproduction, 3. Implementation fidelity, 4. Experimental effort), each with a '0.0 score example', usually a '0.5 score example', and a '1.0 score example' written as 'an agent that ...'. Example of the opening: '# Rubric: Learning Precise Timing with LSTM Recurrent Networks — Figure 4'. Tolerance language is built in: 'It is more important to reproduce the scientific claim and overall trend than it is to get an exact match on specific datapoints' (task prompt G.3). The meta-prompt text itself is not published (not found). Note a small inconsistency in the paper: the text lists five dimensions (visual, claim, implementation, compute use, integrity) while the G.6 rubrics have four sections (the fourth is 'Experimental effort') and Figure C.2 names 'experimental depth, claim reproduction, visual fidelity, implementation fidelity, scientific integrity'.

#### Coding agent as a judge (the rubric judge)

- Plain: A coding agent is given the same workspace as the agent that did the replication, plus the rubric and the gold plot, and scores each rubric criterion between 0 and 1. Because it can read the code, git history and transcript and re-run the code, it checks the process and not just the picture.

> The judge is given 10 minutes to explore these materials and form a judgement on each dimension of the rubric. Each criterion receives a continuous score between 0 and 1, and these per-dimension scores are averaged to give an overall score for the rollout. Crucially, this approach allows the judge to examine fully and potentially re-execute the agent’s code to understand its process and check the robustness of its claims.

- URL: https://arxiv.org/html/2608.13331 , Section 3.2 (Coding agent as a judge)

- Stated conditions: Judge is Codex GPT-5.5; it sees the redacted paper, all the agent's tools, the replication codebase, git history with the final plot, the full interaction trace and the gold plot. 'During training, we sample from the judge three times for each rollout to reduce variance'. The judge prompt itself is not published (not found); only the rubrics are.

#### Research taste (concept) and how they measure it

- Plain: They use 'research taste' for the tacit judgement of what makes a replication good beyond matching a plot: experimental design, scientific practice, faithfulness to the claim, use of resources. They do not give a formal definition; they operationalise it as agreement between the rubric judge and expert human rankings of rollouts.

> Perfectly reproducing a plot is not the same as a successful replication, which also requires strong experimental design, good scientific practice, faithfulness to the claims of the original paper, and effective use of available resources. Ultimately, replication requires “research taste”.  ...  We collect human rankings of agent rollouts to assess the extent to which our rubric-based judge captures human research taste.

- URL: https://inherentlabs.ai/research/training-to-replicate (RL for non-verifiable domains) ; https://arxiv.org/html/2608.13331 Section 3.3 (Human studies)

- Stated conditions: Humans rank 3 or 6 rollouts best to worst, 'instructed to follow their own best judgement about what they would expect a faithful replication to look like, so as to capture human tacit knowledge', must justify rankings; participants are PhD students or graduates 'preferring participants who have published at least one paper at the main conference track of ICML, ICLR, or NeurIPS'; paid GBP 150 per task; 'In total we collect 117 rankings from 20 participants.' Manifesto separately asks: 'What does “AI taste” in the exploration of new knowledge look like?' (https://inherentlabs.ai/) and the paper's conclusion says 'we have created an intelligence layer with a modicum of research taste' (Section 5, Conclusion). A formula or scale for taste: not found.

#### Kendall tau agreement and judge-vs-human results

- Plain: Kendall tau is a rank correlation between two orderings of the same rollouts. They report that the rubric judge agrees with itself much more than humans agree with each other, and agrees with humans only a little better than a plain baseline judge does.

> We measure agreement using Kendall τ, a rank correlation between two orderings (+1 = identical, −1 = reversed). Two independent draws of the rubric judge agree more closely (0.66) than two draws of the baseline judge (0.46) or two humans (0.30). The rubric judge agrees more closely with humans (0.19) than the baseline judge (0.15).

- URL: https://arxiv.org/html/2608.13331 , Figure 3 caption (left); Section 4.1; Appendix F.1

- Stated conditions: Tasks were chosen for maximal disagreement between the two judges (so agreement is informative). F.1: 'We collect 76 rankings from 19 participants ... Participants side with the rubric judge on 63% of disputed pairs, higher than chance but not significantly so (p = 0.109).' The baseline judge uses the same Codex GPT-5.5 with a constant prompt that mirrors the human prompt. Section 4.1: 'there are several tasks on which our rubric judge disagrees with humans, suggesting room for improvement in future work.'

#### Judge noise share (a metric for reward noise)

- Plain: They measure what fraction of the score variation inside a group of rollouts comes from the judge being random, not from real differences between rollouts, as a function of how many judge samples are averaged. The rubric judge needs fewer samples than the baseline judge for the same noise level.

> For each group, we calculate the fraction of the within-group score variance that is caused by judge noise, as a function of the number m of judge samples averaged per rollout. ... In particular, eight baseline judge samples are required to reduce the noise share to the level obtained with three rubric judge samples.

- URL: https://arxiv.org/html/2608.13331 , Figure 3 caption (right); Section 4.1

- Stated conditions: 16 GRPO groups of 8 rollouts each, sampled uniformly across training steps 430 to 461, every rollout scored eight times with each judge; bands are plus or minus 1 SEM over groups. Numerical noise-share values are only in the figure image (not readable in the text).

#### Agent-comparison human study (a conditional claim)

- Plain: Humans blind-ranked a Faraday rollout against one Claude and one Codex rollout, but only on triplets where the judge had put Faraday clearly ahead. The authors say this supports agreement with the judge in that case and says nothing about average quality.

> Of the 41 rollouts examined, humans prefer Faraday over both Claude and Codex in 29, significantly more than chance. ... Importantly, the design of our study does not allow us to draw any conclusions as to whether humans prefer Faraday over Claude and Codex on average.

- URL: https://arxiv.org/html/2608.13331 , Section 4.4 and Appendix F.2

- Stated conditions: F.2: selection rule 'A triplet is eligible when the rubric judge puts Faraday at least 0.2 above both baselines, on the judge’s scale from 0 to 1'; 41 rankings from 11 participants; 'Participants prefer Faraday to Claude in 80% of rankings and to Codex in 88%, and rank it above both baselines in 71%, all significantly higher than chance (p < 0.01)'; ranking is blind.

#### Faraday training recipe: GRPO with multi-sample judge and turn-level credit

- Plain: They fine-tune Qwen3.6-27B with a variant of GRPO using the rubric-judge score as reward, averaging three judge samples and having the judge assign a credit weight to each turn so that important decisions get more of the update. Without turn-level credit assignment training collapsed in their ablation.

> The judge produces a weight distribution u_(k) over turns k which is then normalised such that ∑_(k)u_(k)n_(k) = ∑_(k)n_(k), where n_(k) is the number of tokens in turn k, such that we do not change the overall reward scale.

- URL: https://arxiv.org/html/2608.13331 , Section 3.5 (Long-horizon stability); Appendix B.1 (Figure B.1); Appendix D.2 and Table D.1

- Stated conditions: 'First, we compute the rollout-level reward using the mean of three independent judge evaluations. Second, we instruct the judge to produce turn-level weights'. LoRA rank 128, alpha 128, constant learning rate 6e-6, 128K context, batch of 10 tasks with eight rollouts each from the 242-task train split. Figure B.1: 'with uniform credit assignment it collapses after 50 steps'. Final checkpoint is step 659 of a multi-stage lineage (Table D.1). Done on Kubernetes with NeMo-RL, vLLM, Ray (Appendix H). This is model training; ChipIn does not do it.

#### Coding agent as a tool (CAT) and the 'simple harness'

- Plain: Faraday is a small 27B model that directs a frontier coding agent (Codex) as a tool, with only five basic tools and no hand-built research harness. They argue capability should live in the trained weights, not in an elaborate scaffold.

> Conceptually, we are training a layer of scientific intelligence that sits above existing coding agents, imbued with an intuition about how to handle underspecified research problems. ... Faraday’s scientific capabilities are improved by changing its policy weights, not by complexifying its harness.

- URL: https://arxiv.org/html/2608.13331 , Section 1; Section 3.4 (Simple harness)

- Stated conditions: Five tools: apply_patch, read_file, list_dir, grep_files, shell. 'The coding agent model is a runtime parameter; we use GPT-5.4 mini for most of the training, and GPT-5.5 in the final stage and for evaluation.' After training with the weaker coding agent, swapping in a stronger one improves scores without retraining (Appendix A.2, Figure A.2). The system prompt tells Faraday: 'You are a researcher, not a coder ... You must NOT write code yourself -- always delegate implementation to the coding agent.' Also 'Prior hand-designed multi-agent decompositions are described as 'somewhat brittle and reductive'' (Section 2: 'these modular architectures are somewhat brittle and reductive').

#### Headline results (their benchmark, their judge)

- Plain: On Replica, scored by their own rubric judge, Faraday beats Claude Opus 4.8 and GPT-5.5 (each in its own coding harness) on most tasks. Optimising Codex's prompt for 24 generations does not close the gap.

> Faraday outperforms Claude Opus 4.8 (hereafter, Claude) and GPT-5.5 (hereafter, Codex) on 73% of in-distribution ML tasks, and on 60% of held-out AI-for-science tasks, according to our rubric-based judge. On average, Faraday achieves a 6% improvement over Claude and an 8% improvement over Codex on the test split.

- URL: https://arxiv.org/html/2608.13331 , Section 1 (Introduction); Sections 4.2 and 4.3

- Stated conditions: Same task materials, same 60-minute single-GPU budget, eight rollouts per task, extra-high thinking effort for Claude and Codex, scored by the same rubric judge. 4.2: 'Task performance decreases with publication year for every agent', and 'AI-for-science papers are generally harder to replicate than ML research papers across agents'. 4.3: 'the gain from post-training does not appear to be reachable by prompting.' The training and judging models partly overlap in vendor with the baselines (Ethics statement, Conflict of interest).

#### Where AI scientists fail: observed failure modes in rollouts

- Plain: By reading the best rollouts of the baselines against Faraday, they found frontier coding agents often fake or shortcut the mechanism being tested, run it too narrowly, or pick a flattering result. Faraday avoids these more often.

> First, Faraday implements the mechanism an experiment is designed to test, whereas the baseline hardcodes the expected output or falls back on an oversimplified method, failing to replicate the main claim of the figure. Second, Faraday is more thorough in the scope of its experiments, reproducing more of the original experiment without unnecessary omissions.  ... [Introduction:] it implements the mechanism behind the claim rather than hard-coding outputs, it scales down in a way that remains faithful to the paper’s experimental scope, and it avoids shortcuts that would flatter its own result.

- URL: https://arxiv.org/html/2608.13331 , Section 4.4 and Table 1; Section 1

- Stated conditions: Selected by hand from the rollouts with the largest judge margin (so they are showcase cases, not rates). Table 1 examples verbatim: Darwin-Godel Machine 'The baseline instead hard-codes a putatively discovered agent, bypassing the search that the experiment is meant to demonstrate.'; Voyager 'a hard-coded, pre-populated library including target-solving skills'; LSTM timing 'steers the network towards the desired behaviour through its initialisation and auxiliary losses, and then selects a favourable checkpoint that shows the desired result.'; GNoME 'the best Codex rollout uses one seed per scaling point with no reported uncertainty ... Codex draws both sets from one generator call that takes no temperature argument, so the claimed shift reported on the axis is not supported.'; ChemVAE 'every molecule in its figure is retrieved from the dataset rather than generated by the model.' Rate numbers for each failure mode: not found.

#### Failure modes named in the optimised Codex prompt (Appendix G.5)

- Plain: The prompt that Claude wrote after reading 24 generations of Codex rollouts and judge feedback lists the specific ways the baseline loses points. It reads as a checklist of how an AI scientist goes wrong: misreading constants, skipping the real experiment, stopping early, cropping plots, and write-ups that contradict the logs.

> Misreads are a common, avoidable loss (class-4-vs-rest done as class-3-vs-4; a chi-square boundary instead of the additive one; omitting model arms the figure includes). ... The most-ignored rule: agents submit at minute 12–20 with 40+ min unused. ... Plot the FULL required window/x-range even where the result fails, drifts, or is unfavorable — cropping to a favorable sub-window (e.g. a single spike) is both a trend loss and an integrity violation.

- URL: https://arxiv.org/html/2608.13331 , Appendix G.5 (Optimised Codex prompt); Section 4.3

- Stated conditions: This prompt is a machine-optimised artefact: 'Claude Opus 4.8 then rewrites the prompt based on all previous rollouts in the filesystem, including the judge’s feedback', it did 'not perform meaningfully better than the original prompt', so these are failure observations and rules the judge penalises, not a validated method. It also says: 'Never fit/select params on the eval stream, run a lr≈0 pass, or pick a data window/split/seed after seeing the trend', 'Rigor: ≥3 seeds/runs AVERAGED with real error bars', 'Fix hyperparameters before seeing results; any tuning applies symmetrically to all conditions and is disclosed', and two attestations in the write-up: 'real slice: <...>' and 'budget used: <N>/60 min' read 'verbatim from the environment timer'. Also: 'every quantitative claim in writeup.md ... must be READ OFF the final artifacts (code/CSV), not estimated or copied from the paper'.

#### Authenticity rule: never simulate or fabricate (Faraday system prompt)

- Plain: The agent is told that fabricated or hard-coded results score zero, but that a clearly documented scaled-down real run is acceptable. This is the practical form of the 'scientific integrity' rubric dimension.

> **Never simulate or fabricate experiments.** Always run experiments for real. Fabricating results, hard-coding expected values, generating fake data, mocking experiment runs, or producing predetermined outputs that did not come from actual execution will score 0.

- URL: https://arxiv.org/html/2608.13331 , Appendix G.1 (Faraday system prompt), section '# Authenticity'

- Stated conditions: 'If the original scale of an experiment is infeasible within the available compute and time, run a clearly-documented scaled-down version (smaller model, fewer steps, fewer seeds) -- that is acceptable; fabrication or simulation is not.' The judge is told 'to reward best-effort within constraints over fabrication' (G.3).

#### Judging in hindsight versus a verifiable reward (their stance on reward hacking)

- Plain: They argue a fixed, verifiable reward is a target that agents learn to game, while a judge reading the whole rollout afterwards is a moving target. They explicitly say it is not yet shown that this reduces reward hacking at scale.

> Defining a verifiable reward necessitates specifying an evaluation procedure in foresight, which becomes a fixed target for manipulation. By contrast, judging entire rollouts in hindsight is a moving target. ... It remains to be seen whether training on open-ended tasks can scalably ameliorate reward hacking.

- URL: https://arxiv.org/html/2608.13331 , Section 5 (Beyond verifiable rewards)

- Stated conditions: Stated as a possible 'side effect' ('A side effect of this reorientation may be that agents are less exposed to incentives for reward hacking') with no experiment. Related work (Section 2) criticises hill-climbing verifiable benchmarks: 'this approach suffers a critical limitation: the innovations that agents uncover do not tend to be generalisable. In other words, they are adaptations but not exaptations'. Homepage: 'Blind optimisation of narrow metrics, whether at the level of an AI model or a human organisation, often proves counterproductive to breakthroughs and anathema to cooperation.' (https://inherentlabs.ai/ , Section II).

#### Imagined (counterfactual) replications

- Plain: To test whether the agent does more than recall papers, they rewrote five train and five test papers into two variants each: same claim on a different dataset, or the same setting with a changed (often reversed) claim. The judge preferred Faraday on 19 of 20, but the judge was never validated on such tasks.

> Faraday’s rollouts are preferred to Codex’s by the judge on 19 of the 20 tasks. In a weak sense, Faraday not only replicates better than a frontier model; it also innovates better. However, we must caution that our rubric judge was never validated on imagined tasks, and so future work is warranted to validate this claim.

- URL: https://arxiv.org/html/2608.13331 , Section 5 (Towards innovation); Appendix F.3, Tables F.3 and F.4

- Stated conditions: F.3: '(a) keeps the paper’s claim but swaps the dataset or environment, and (b) keeps the setting but changes the claim, usually reversing it. In both cases the “gold plot”, its caption and the paper text are rewritten together, so the published result is no longer the target and recall is of limited benefit.' Variants generated by Claude Opus 4.8. Example from Table F.4: 'The model handles untested proteins just as well as untested compounds.'

#### Redaction as decontamination and cheat detection

- Plain: The original figure is removed so the agent cannot copy it, and so the judge can tell if the agent downloaded or reverse-engineered the original. They say pre-training contamination of the paper text is not a problem because the process data was never recorded.

> The decision to redact the figure was taken to decontaminate the context of the agent and thus encourage a focus on rigorous replication process, and to make it easier for the judge to detect any cheating behaviour, such as reverse engineering the data by downloading the original plot.

- URL: https://arxiv.org/html/2608.13331 , Appendix D.1

- Stated conditions: They accept contamination of paper text ('Undoubtedly some of the papers we choose, including their figures, are in the pre-training dataset') and take it into account in reading results; three of eight full-scale tasks were from papers newer than the models' knowledge cutoffs (A.1).

#### Stated view of the human's role

- Plain: Inherent says AI should not replace scientists but form a human-plus-machine collective, keep humans involved and the insights legible, and keep humans in control; the paper adds that humans should keep the skill to inspect agents' results. The human acts as expert ranker, tacit-knowledge source and overseer; the clinician-sets-the-bar idea is the team's own, not theirs.

> We believe that AI’s promise lies not in automating science, but in enabling a new kind of collective intelligence that leverages the comparative advantages of humans and machines.  ...  To preserve the joy of knowledge discovery, we must build systems that preserve human involvement and produce legible insights.  ...  Even as and when AI systems demonstrate sufficiently strong performance to serve as reliable judges of replicability, it will remain important for humans to cultivate the skills necessary for paper replication and to inspect the results of agents such as Faraday.

- URL: https://inherentlabs.ai/ (manifesto, Intro and Section II); https://arxiv.org/html/2608.13331 Ethics statement (Awareness of limitations)

- Stated conditions: Also: 'enabling us to discover new knowledge while firmly keeping humans in the loop' (https://inherentlabs.ai/research/training-to-replicate, Future directions); 'AI that transforms invention must be equipped with deep aesthetic intuition over hypotheses, magnifying the agency of human scientists' and 'By threading self-improvement through human-machine cooperation, we reap the benefits of rapid progress while keeping humans in control' (homepage). Human feedback in the paper: authors of four replicated papers commented on Faraday's replication ('part b and c look very good', 'the problem selected is probably too easy', 'code slop is off-putting'). The paper does not describe a human who sets a threshold or acceptance bar; 'clinician' or any domain-expert gatekeeper: not found.

### Where it applies in our pipeline

#### 1. Replica-style replication task with an auto-generated rubric (task triple, five dimensions, hidden gold, judge scoring 0 to 1)

- Where: Pipeline stage 2, the step where the system 'picks or trains a reference model on recordings' before candidate shrinking starts. Frame it as: before the search starts, can the agents re-derive a published reference result under a fixed budget?

- Already exists: Partly. The product already picks or trains a reference model on recordings, and it already uses Claude or OpenRouter models as agents and gpt-oss-120b to write summaries. It has no redacted-paper task, no rubric and no judge, so nothing of the Replica format exists yet; the earlier team notes proposed a 'Replicate first' card but with an ad hoc pass/fail band.

- To build, and the number to report: One task folder in Replica's format: paper.pdf with ONE results figure or table redacted (a published small-EEG or sensor-model paper whose data are public and whose numbers the team can check itself; which paper: to be chosen, not decided here), caption.md, prompt.md copied in structure from Appendix G.3 (real experiments only, scaled-down allowed and documented, plot.png and writeup.md required, git history assessed, no downloading the paper's own results), and a time and compute budget. Then rubric.md in their shape: opening paragraph stating the paper's claim, four headed sections (Visual fidelity, Claim reproduction, Implementation fidelity, Experimental effort) with 0.0, 0.5 and 1.0 'an agent that ...' examples as in G.6, written by an LLM from the paper text and caption with the gold figure withheld (as 3.2 does; the team can hand-write it if short on time). A judge script gives an agent (Claude CLI or OpenRouter) read access to the agent's workspace, git log, transcript and the hidden gold figure, scores each section 0 to 1, averages, and is sampled 3 times. Dashboard: one card 'Replication check' showing the five or four dimension scores (mean of 3 samples, with the spread) and the reproduced headline metric (e.g. sensitivity and false-alarm rate) beside the paper's reported value, the tolerance, and 'budget used' read from a timer; the search only starts from a replicated reference. Number reported: mean rubric score 0 to 1 over 3 judge samples, and absolute gap of the reproduced metric to the paper's within a stated tolerance, measured by the judge script reading the agent's results file. Risk: the Replica paper's rubric was written for ML-paper figures; a medical-sensing figure may need a rewrite of the examples, and the whole task needs a paper whose result really replicates (Appendix E warns 'some tasks represent results that simply do not replicate').

- Sentence for the demo: For the reference model we built one replication task in the style of the Replica paper from Inherent Labs, a published result with its figure removed, a budget and a rubric that scores claim, implementation and integrity, and our agents have to reproduce it before the search starts. This is our own task and judge, not Replica and not Inherent's.

- Why their people would accept it: It is the actual Replica recipe (redacted figure, per-task rubric written without the gold plot, coding-agent judge with workspace access) applied to a new domain and honestly labelled as the team's own, with no score claimed as theirs.

#### 2. Scientific-integrity dimension and the 'read off the artifacts' rule: claim-versus-artifact check on every agent's summary and the final report

- Where: Stage 2 (spec and reference agents), the gpt-oss-120b run summaries, and stage 6 (the report returned with the chip). Applies the rubric's integrity dimension and the G.1/G.5 rules to the places where text claims numbers.

- Already exists: Largely yes for the numbers that matter: the pipeline measures 2,330 gates, 256 candidates per batch at 1,626 per minute, and 3,880 of 3,880 windows bit for bit, and the netlist is formally proven equivalent. What the notes do not show is a check that each number in a language-model-written summary matches the machine's measured JSON, or that the agent cannot have 'fabricated or hard-coded' a result.

- To build, and the number to report: A small script claims_check.py: extract every numeric claim from the gpt-oss-120b summary and the report (regex on numbers with units, or one structured-output call listing claims), look each up in the run's results JSON (gates, windows verified, candidates, throughput, sensitivity, false-alarm), and flag any number that is absent or differs. Add the two attestations from G.5 to the report, written from the final run only: 'real slice' (what actually ran: reference trained or reused, GPU batch, synthesis, proof) and 'budget used' (wall-clock read from the run log, not estimated). Dashboard: a 'Claims checked: N of N match artifacts' line on the report, and a red mismatch list if any. Number reported: count of claims matching artifacts out of claims extracted, measured by the script.

- Sentence for the demo: Following the integrity rule in the Inherent Labs Faraday paper, that every number in a write-up must be read off the final artifacts, our report is checked claim by claim against the measured results, and it lists what really ran and the time used.

- Why their people would accept it: It uses their own 'scientific integrity' dimension and their 'never simulate or fabricate, read every number off the artifacts' rule exactly as written, and makes no claim about their results.

#### 3. Hindsight and held-out discipline: selection on validation, one untouched test, seeds with error bars, judge hidden from the proposers

- Where: Between stage 3 (thousands of candidates trained in one batch) and stage 5 (winner verified), and the proposing agents of stage 2. Guards against the failure modes 'selects a favourable checkpoint', 'one seed per scaling point with no reported uncertainty', and 'pick a data window/split/seed after seeing the trend' (Table 1, G.5), and uses 'The judge rubric is also hidden from the model during training'.

- Already exists: Unknown, to be confirmed by the team: the notes record that the winner is verified on 3,880 test windows, but not whether those windows were also used to rank the thousands of candidates (a best-of-thousands selection effect), nor whether the proposing agents can see the test windows or the clinician-bar scorer. The batch trainer makes re-seeding cheap, but no seed-spread number is in the notes.

- To build, and the number to report: (a) Split recordings by patient or recording into train, validation and a frozen test set, rank and choose the winner on validation only, evaluate the winner on the frozen test set once, and log a hash of that single evaluation call. (b) Retrain the chosen design and the next few runners-up with 3 to 5 seeds in the existing GPU batch and report mean and spread of sensitivity and false-alarm rate against the clinician bar. (c) Do not pass test windows or the final bar scorer to the proposing agents. Dashboard: 'Selected on validation, tested once on held-out recordings', and the seed spread beside the headline metric. Numbers reported: held-out sensitivity and false-alarm rate with the seed range, and whether the winner still clears the bar at the worst seed, measured by the trainer's seed runs.

- Sentence for the demo: Inherent Labs' replication paper catalogues how AI scientists fail, such as picking a favourable checkpoint or reporting one seed with no uncertainty; our pipeline picks the design on validation data, tests it once on held-out recordings, and reports the spread across seeds.

- Why their people would accept it: It answers failures they actually documented (favourable checkpoint, no uncertainty) with a standard practice, and does not claim to have their method or numbers.

#### 4. Measured judge noise: sample the rubric judge three times and report the spread

- Where: Wherever application 1 or 2 uses an LLM judge (the replication card and the report check).

- Already exists: No. The product has no LLM judge yet; this only exists if application 1 is built.

- To build, and the number to report: Call the judge 3 times per task (their training setting), report the mean and the range of the overall score and per-dimension scores, and optionally also run the same judge once with a constant generic prompt without the per-task rubric. Dashboard: score plus 'spread across 3 judge samples'. Number reported: standard deviation or range over 3 samples; if time allows, the share of variance due to judge noise on 8 samples versus rollout differences using their Figure 3 (right) definition. Measured by repeating the judge call.

- Sentence for the demo: Because an LLM judge is itself noisy, as Inherent Labs measured for their rubric judge, we run ours three times and show the spread beside the score.

- Why their people would accept it: It uses their stated reason for per-task rubrics and multi-sample judging (noise in the reward) and does not overstate the judge.

#### 5. Imagined replication variant: same claim on a different dataset, or reversed claim

- Where: A single extra run of the whole pipeline (stages 2 to 5) on a second sensing task or a second recording set, once the main run is done. Tests that the system reproduces a procedure, not one memorised EEG case.

- Already exists: No for the pipeline as a general test, although the team's own notes mention several candidate sensing areas (EEG, fertility, dialysis, neonatal), so the second recordings may already be at hand; whether the pipeline runs unchanged on them is not confirmed.

- To build, and the number to report: Choose one second dataset and run the identical pipeline with no code change; report whether the clinician bar is met, the gates and the formal equivalence, and the number of manual edits needed (target: zero). For the reversed-claim variant, a second spec where the claim is expected to fail (a bar the data cannot meet) to show the system returns 'no chip meets the bar' instead of a chip. Dashboard: a row 'second dataset, same pipeline, zero code edits' and the pass or no-chip outcome. Measured by diffing the repo and the run log.

- Sentence for the demo: Inherent Labs tested their agent on 'imagined' variants of papers, with a new dataset or a reversed claim; we ran our pipeline on a second dataset without changing any code.

- Why their people would accept it: It follows their own variant construction (swap dataset, or change the claim) for a generalisation test, and does not cite their 19-of-20 result as evidence for ChipIn.

#### 6. Human-versus-judge ranking agreement (Kendall tau) on a handful of candidates or reports

- Where: Stage 2 summary or stage 6 report, alongside application 1 or 2.

- Already exists: No.

- To build, and the number to report: Have one or two people blind-rank 3 to 6 candidate designs or agent reports by quality, compute Kendall tau between that ranking and the rubric judge's order (scipy.stats.kendalltau), and show 'agreement with a human ranking, n tasks, tau' on the dashboard. It is only a sanity check with a small n and must say so; their own human-judge tau was 0.19 and not significant for the judge comparison.

- Sentence for the demo: Following the Inherent Labs paper, we compare our judge's ordering to a person's blind ordering with Kendall tau on a handful of cases, and we report the sample size.

- Why their people would accept it: It uses their metric and their human-ranking protocol at a scale they would call a sanity check, and the numbers shown are honest about n.

### Do not

- Saying ChipIn uses, is built on, is trained like, or is validated by Faraday, Replica, or Inherent. The paper releases nothing usable (no code, weights, API, tasks or judge prompt found in the text; only example rubrics and prompts), and the only link is event support. The paper's own contact line is 'we would be delighted to hear from you at faraday@inherentlaboratories.com' (Section 5, Community engagement), not an offer of access.

- Calling the product's agents 'AI scientists with research taste'. In their text taste is measured as ranking agreement with PhD-level humans on paper replication, and even there 'The rubric judge agrees more closely with humans (0.19) than the baseline judge (0.15)' and 'Participants side with the rubric judge on 63% of disputed pairs, higher than chance but not significantly so (p = 0.109)' (Figure 3 caption; F.1). 'Research taste' is their concept; the team has no measurement of it for its agents.

- Presenting their headline numbers (73%, 60%, 6%, 8%) as evidence about chip design or as the product's own performance. Each is 'according to our rubric-based judge' on paper replication, ML and AI-for-science papers, Section 1; the human study 'does not allow us to draw any conclusions as to whether humans prefer Faraday over Claude and Codex on average' (Section 4.4).

- Calling the bit-for-bit and formal netlist-versus-model check a 'replication' in their sense. Replication in the paper means re-deriving a published claim from the paper text under uncertainty: 'The act of replication typically illuminates details that were previously underspecified' (Abstract). Gate equivalence to a given model is deterministic checking with a known target; it says nothing about whether the model is right for the clinical task.

- Describing ChipIn's search as the kind of reward-free, open-ended science Inherent's work targets. ChipIn optimises a fixed, verifiable target (smallest chip meeting a bar), which their Related work calls hill-climbable benchmarks whose findings 'do not tend to be generalisable', and the manifesto says 'Blind optimisation of narrow metrics ... often proves counterproductive to breakthroughs'. Present ChipIn as a verified engineering search; do not claim it is 'AI for science' in their sense, and do not claim kinship on reward design.

- Claiming ChipIn solves reward hacking or that its pipeline has their anti-hacking property. They state 'It remains to be seen whether training on open-ended tasks can scalably ameliorate reward hacking' (Section 5), and ChipIn uses a verifiable reward, which they call 'a fixed target for manipulation'. Hiding test data from proposers (application 3) is ordinary held-out hygiene; credit their rubric-hiding as the source only for that one idea.

- Equating 'the clinician sets the bar' with their human-in-the-loop view. Their stated role is collective intelligence, human involvement, legible insights and humans able to inspect agent results; a human threshold is not described anywhere ('clinician' not found). Also the paper does not say science 'should' be done a particular way.

- Claiming the product's model-per-job design is their 'coding agent as a tool' (CAT) method. CAT is a trained small outer agent directing a frontier coding agent, with the outer model post-trained by RL on a rubric reward; ChipIn trains no outer agent and has no learned delegation policy.

- Claiming the product 'innovates' because Faraday 'innovates better' on imagined tasks. The authors call it only 'in a weak sense' and 'our rubric judge was never validated on imagined tasks' (Section 5).

- Calling the team's replication check 'Replica', or scoring a ChipIn run 'on Replica', or implying their judge scored it. Replica is 310 specific tasks from 100 ML and AI-for-science papers; the team's task would be its own, in the same style, with its own rubric and judge.

- Citing the redaction, rubric or judge as validated for medical-sensing work. Validation is only for ML paper figures with 117 human rankings from 20 participants; the paper says the judge was not validated at larger scale ('we did not validate our rubric judges with human ratings on rollouts at this scale', A.1) or on imagined tasks.

- Using their G.5 prompt rules as 'Inherent's method'. G.5 is a prompt written by Claude from Codex's failed rollouts, and it 'does not perform meaningfully better than the original prompt' (Section 4.3); quote it as listing observed failure modes only.

- Presenting a pass on the replication card as proof the reference model is correct. A replication can still fail through no fault of the agent: 'it failed in several cases where we have confidence that the original result was obtained rigorously and reported honestly' (Ethics statement), so a miss is not evidence against the paper and a hit on one paper is not general validation.

### Their own open problems

- Judge disagreement with humans: "However, there are several tasks on which our rubric judge disagrees with humans, suggesting room for improvement in future work." (https://arxiv.org/html/2608.13331 , Section 4.1). ChipIn can speak to it only by showing a judge-versus-human check with an honest n (application 6).

- Judge not validated beyond its scope: "The caveat is that we did not validate our rubric judges with human ratings on rollouts at this scale, an important step for future work." (Appendix A.1) and "our rubric judge was never validated on imagined tasks, and so future work is warranted to validate this claim." (Section 5, Towards innovation).

- Average human preference unproven: "Gathering conclusive evidence for this preference would require a larger-scale study across a randomly selected set of tasks, and is an important direction for future work." (Section 4.4).

- Non-replicable results and honest reporting: "Inevitably, some tasks represent results that simply do not replicate. ... Were we to scale the task space, we would need to develop judges that recognise non-replicability and agents that robustly test and honestly report it." (Appendix E). ChipIn can speak to this by showing it can return 'no chip meets the bar' (application 5) and by reporting a failed replication without hiding it.

- Reward hacking: "It remains to be seen whether training on open-ended tasks can scalably ameliorate reward hacking." (Section 5, Beyond verifiable rewards), and on the page: "With an eye to safety, we are investigating how our methods might advance scalable oversight and ameliorate reward hacking." (https://inherentlabs.ai/research/training-to-replicate , Future directions). ChipIn's formal equivalence step is an example of a check an agent cannot argue with, but it addresses model-versus-gates, not reward design.

- Legibility and interpretability of AI results: "How can we reap the benefits of rapid counter-intuitive discoveries while ensuring that findings remain interpretable to humans?" (https://inherentlabs.ai/ , Section II). ChipIn's output is an inspectable gate netlist with a report and an equivalence proof, which the team can present as an example of a verifiable, human-checkable artefact (without claiming it answers the question).

- Benchmarks for a system choosing its own reward: "How can we craft rigorous benchmarks for a system that controls its own reward?" (https://inherentlabs.ai/ , Section III). In ChipIn the bar is set by a human and fixed before the search, so the agents do not control their own reward; this is a contrast, not a solution.

- Human-machine teaming: "What are the most effective methods of human-machine teaming for scientific research?" and "What is the right interface to enable effective research collaboration between many humans and many AI agents?" (https://inherentlabs.ai/ , Sections I and II). ChipIn's human-sets-the-bar, agents-search, machine-verifies split is one concrete interface; the team can offer it as a data point, not an answer.

- Inner and outer model sizing: "Establishing the optimal cost-benefit tradeoff between the sizes of the inner and outer agents is an interesting topic for further study." (Section 5, CAT). ChipIn uses different models for different jobs (Claude, Inkling 2 Mini or another OpenRouter model, gpt-oss-120b) and could report which job needed which model, but this is not their question about a trained outer agent.

- Harness versus weights: "it is an empirical question whether the demands of scientific judgement must match or exceed those of engineering execution in the long run." (Section 5, CAT). Not something ChipIn tests.

### Not read

- The reference list of the paper (the bibliography between Acknowledgements and the Appendix) was not read; only in-text citations were seen.

- Figure and chart images were not readable as text: Figure 2 legend numbers (mean scores per agent), Figure 3 dots and noise-share curves, Figure 4 and 5 bar values, Figures A.1, A.2, B.1, C.1, C.2 and C.3 plot contents. Only their captions were read.

- Appendix B.1, B.2 and C sections consist only of figure captions in the HTML; no separate prose exists for them (read as captions).

- Tables F.1 and F.2 (task lists for the human studies) were read only for their first rows and structure; Table F.2's later rows were not read row by row. Tables F.3 and F.4 were read in full.

- The text of the meta-prompt that generates rubrics, and the judge's own prompt, are not in the paper and could not be read (not found). Only the three example rubrics in Appendix G.6 and the agent-side prompts G.1 to G.5 are published.

- No second essay or paper by Inherent was found: the homepage manifesto is the only essay, and the research index lists one item. Not checked: any blog, GitHub, Hugging Face, talks or interviews, including the Saturday 12:00 to 12:30 event talk mentioned in the team's notes (no transcript exists to read); the Privacy page; the arXiv abstract and PDF versions (only the HTML version was read).

- Whether Faraday, Replica tasks, judge or weights are available to hackathon teams: not found in any primary text read. The only contact in the paper is faraday@inherentlaboratories.com and in the manifesto curious@inherentlaboratories.com.

- Whether the team's winner selection and the 3,880 test windows are disjoint, and whether the proposing agents can see the test windows or the bar scorer: not in the notes read (the team must confirm before using application 3's wording).

- Which published EEG paper the replication task should use, and whether its numbers replicate, was not investigated (outside the task scope); application 1 depends on that choice.

## Fractile and ARIA

### What was read

- READ IN FULL (text extracted and read end to end): Fractile manifesto page https://fractile.com/manifesto (its HTML title is 'The future of AI scaling | Fractile', dated 13 May 2026, by Walter Goodwin; the How we think page lists it twice, once as the essay 'The future of AI scaling' and once as 'Fractile raises $220M...', and both link to manifesto.html, so the earlier notes' 'not found' was this same page). Fractile How we think page https://fractile.com/how-we-think (all items listed: 3 podcasts, 1 essay, 5 press links). Fractile home page and the first part of the Join the mission/jobs page.
- READ IN FULL as transcripts (YouTube auto-captions pulled with yt-dlp, read end to end; captions spell the company 'Fractal'): 20VC with Harry Stebbings, 'The AI Compute Crisis: Why We Need Thousands of Times More Computing Power' https://www.youtube.com/watch?v=UZ8eYaAf08M ; Forecast 2050, 'The Future of Chips in the AI Era' with Walter Goodwin and Sir Robin Saxby https://www.youtube.com/watch?v=zPOyb4nCRRs ; No Priors, 'Frontier Chips for Frontier AI Labs' https://www.youtube.com/watch?v=OpeCP4wCxkA (the Spotify episode linked from How we think has the same title, so I treated it as this episode).
- READ IN FULL: ARIA Scaling Compute programme thesis v2.0, accessible PDF (all 320 lines of extracted text incl. references list) https://www.aria.org.uk/media/mcgn0i55/aria-unlocking-ai-compute-hardware_accessible.pdf
- READ: ARIA Scaling Compute call for proposals v1.0 13.03.24 https://www.aria.org.uk/media/22ehvylu/aria-scaling-compute-call-for-proposals.pdf (text through Section 5, plus keyword scan of the rest; Figure 2 and Figure 4 viewed as page images). ARIA TA4 Benchmarking RFP 17 Feb 2025 https://www.aria.org.uk/media/43qfanm1/scaling-compute-rfp-benchmarking.pdf (first ~200 of 364 text lines).
- READ IN FULL: ARIA Scaling Compute programme page, Funded projects page, Funding page, Scaling Inference Lab page (including cluster descriptions that sit in the page's embedded data) under https://www.aria.org.uk/opportunity-spaces/nature-inspired-computation/scaling-compute/
- READ IN FULL: ARIA AI in Science page https://aria.org.uk/ai-in-science ; AI Scientists page https://aria.org.uk/ai-in-science/ai-scientists ; Work in progress page https://aria.org.uk/ai-in-science/work-in-progress ; the AI Scientist call document v1.0, 14 Oct 2025 (all 9 pages) https://aria.org.uk/media/za3mj5h1/ai-scientist-solicitation-call-document_accessible.pdf ; CTO update 'Why we're exploring AI Scientists' (30 Oct 2025) https://aria.org.uk/insights/2025/why-we-re-exploring-ai-scientists-update-1 ; 'Can an AI Scientist really discover knowledge?' (5 Jun 2026, the Albert benchmark) https://aria.org.uk/insights/2026/can-an-ai-scientist-really-discover-knowledge
- Downloaded files were temp copies under /tmp and have been deleted by absolute path (two older files fr-terms.pdf and fr-terms.txt in /tmp are not mine and were left). Nothing was signed up for, logged into or submitted.

### Their methods

#### Time from query to output as the limit (Fractile's thesis, in tokens per second)

- Plain: Fractile says the key limit on frontier AI is how long an output takes to produce, not only whether the model is capable. Its unit is tokens per second for one output stream, with a stated gap between today's roughly 40 and a target of roughly 1,200.

> "At the ~40 tokens per second or so at which these models tend to run on existing chips, a single output of this length takes a month to complete. ... To compress that month into a day, we will need to generate output at ~1,200 tokens per second, while handling the complexity and capacity challenges of operating large models at very long contexts." (and) "time from query to output is the key limit to frontier capabilities"

- URL: https://fractile.com/manifesto (body, paragraphs 2 and 5)

- Stated conditions: The 100-million-token output is for LLM reasoning on hard problems at very long context on 'existing chips'. Applies to sequential LLM generation. Fractile gives no energy per operation, no pJ/token and no bytes per token in the manifesto: not found.

#### The memory wall: bandwidth lags arithmetic, and every generated token reloads the weights

- Plain: Fractile counts arithmetic (flops) and bandwidth to memory as the two headline specs of a chip. Arithmetic grew about a million times in 25 years and bandwidth about 40 times, so token generation is limited by how often the weights can be loaded, not by the maths.

> "We've scaled it about a million fold in the last 25 years on these chips. Bandwidth by contrast is kind of much more intrinsically physics limited. We've scaled it about 40 fold in the same time. So you know it's lagged behind the flop scaling about 25,000 times." and "Every time I go and generate one of those words, I'm loading from that memory over that limited bandwidth all of the weights of my model. ... I cannot load the weights of the model from memory into that processor more than let's say 80 times per second."

- URL: https://www.youtube.com/watch?v=UZ8eYaAf08M (20VC, answer on the memory wall) ; the manifesto says "above all from memory bandwidth that has failed to scale on current architectures" at https://fractile.com/manifesto

- Stated conditions: Stated for autoregressive LLM inference on GPU-class chips with HBM; the 80 tokens per second is an example for 'a very large frontier model'. The contrast with arithmetic is Goodwin's podcast framing, not in the manifesto.

#### Flops per byte and model flops utilisation (MFU)

- Plain: Chips offer a fixed ratio of arithmetic to bandwidth, while attention wants far more bandwidth, so the arithmetic units sit idle. The metric labs track for this is MFU, the share of the chip's peak flops actually used.

> "you might have 10 terabytes per second of bandwidth to memory, but then you might have 10 petaflops of compute capability. ... roughly kind of 1,000 to 1 basically." ... "model flops utilization, which is as I'm running this workload, even though I've got that 10 petaflop chip, I may maybe actually only using you know, 100 teraflops and I'm at 1% MFU. Effectively, I'm paying 100 times more per flop because I've paid for the silicon anyway." and for attention "It's more like a 1 to 10 per byte that I load."

- URL: https://www.youtube.com/watch?v=zPOyb4nCRRs (Forecast 2050, answer on the memory wall)

- Stated conditions: Illustrative round numbers said aloud, for LLM decode/attention on HBM GPUs; not measured data in a document.

#### Breaking the inference Pareto frontier of cost versus latency

- Plain: Fractile frames inference economics as a trade-off curve between cost and latency and says its goal is to move off that curve. Goodwin adds that on HBM chips you are 'either slow and efficient or fast but deeply inefficient', measured as tokens per second per megawatt.

> "develop systems that break the trade-off curve, reject the inference pareto frontier of cost-versus-latency" (manifesto) ; "On these chips you can either be sort of slow and efficient in generating tokens or fast but but deeply inefficient, sort of far fewer tokens per second per megawatt of power for instance." (20VC)

- URL: https://fractile.com/manifesto (paragraph 'Making this possible begins with people') and https://www.youtube.com/watch?v=UZ8eYaAf08M

- Stated conditions: Cost-versus-latency curve of LLM serving at data-centre scale. No numeric axis or formula is published.

#### Intelligence per megawatt (and cost per gigabyte of memory)

- Plain: Goodwin's stated unit for the data-centre future is how much output a fixed power and space budget gives. For serving many users he says the economics collapse to the cost per gigabyte of memory.

> "squeeze more and more and more, dramatically more intelligence per megawatt per rack in one of those data centers." (20VC) ; "the economics actually collapse down to uh essentially a kind of cost per gigabyte of the memory that you're employing." (No Priors)

- URL: https://www.youtube.com/watch?v=UZ8eYaAf08M and https://www.youtube.com/watch?v=OpeCP4wCxkA

- Stated conditions: Spoken framing for data-centre inference for thousands of users; no formula or measured value.

#### Amdahl's law as a theory of bottlenecks (speed up the trials, not only the thinking)

- Plain: Goodwin applies Amdahl's law to chip design and AI research: once the thinking part is fast, the parts that cannot be sped up (fab cycle time, slow layout algorithms, experiments) set the pace. So he says to accelerate the trials with approximations and keep a trusted final check.

> "Amdahl's law, right? Like everything I can parallelize becomes very very fast and the part that I can't parallelize doesn't." ... "could you have some kind of fuzzy placement algorithm in the meantime that gets you almost all the way to your final design, helps you iterate faster, you know, I think chip design is not going to change in the final sign-off for quite some time. ... the final check mark that says this thing is what we call DRC and LVS clean."

- URL: https://www.youtube.com/watch?v=OpeCP4wCxkA (No Priors, answer on AI for chip design) ; also https://www.youtube.com/watch?v=zPOyb4nCRRs ("it's basically a theory of bottlenecks")

- Stated conditions: Said about chip design flow and AI-guided experiments; fab cycle quoted as 'three to five months even in a kind of super hot lot scenario'. It is a qualitative principle, not a published result.

#### Test-time compute scaling: sequential depth plus a parallel swarm, and ensembling

- Plain: Fractile's founding bet is that spending more compute at inference (search, long reasoning, many agents) improves results, from AlphaGo's tree search to reasoning models. Goodwin names two axes, many parallel agents and long sequential runs, and the simple form of ensembling by majority answer.

> "I've both got 10,000 parallel agents all generating their own chains of thought. And then they're running for 80 hours." (20VC) ; "the idea of ensembling on any model output where you just run the same model ... multiple times over effectively the same input and you take the kind of, you know, the most frequent answer" (Forecast 2050) ; manifesto: "AlphaGo achieved superhuman performance through not just running a neural network once to pick one particular next move, but running a tree search over many possible futures"

- URL: https://www.youtube.com/watch?v=UZ8eYaAf08M ; https://www.youtube.com/watch?v=zPOyb4nCRRs ; https://fractile.com/manifesto

- Stated conditions: About LLM agents on hard problems. The manifesto stresses that 'Serious intellectual work involves many sequential steps, each dependent on the last', i.e. the parallelism they discuss is on top of sequential chains.

#### Opinionated, workload-specific chips (give up generality to win 10x)

- Plain: Goodwin says a good specialised chip should drive a 10x gain somewhere by giving up something elsewhere, and that this only pays if the workload is stable long enough to repay the chip. He also says hardware and workloads pull each other (the 'hardware lottery') and he studies 'scaling laws for bandwidth'.

> "if everybody loves your chip when you ship it to them, you've you've probably failed to be sufficiently opinionated because it, you know, it should be maybe constraining. It should be, uh, you know, driving a 10x somewhere by sacrificing some other capability somewhere else." (Forecast 2050) ; "if the long tail of of things that you wanted to run was also a fat tail, I think this might change. ... You'd have to build something which was less opinionated, more general purpose." (Forecast 2050) ; "we get to explore for instance internally these kind of ideas of like scaling laws for bandwidth" (No Priors)

- URL: https://www.youtube.com/watch?v=zPOyb4nCRRs ; https://www.youtube.com/watch?v=OpeCP4wCxkA

- Stated conditions: Their specialisation is for a concentrated LLM workload run by 'five or six or seven major companies', with 'a 3 to 5 year amortization window'. Not a claim that one-off chips per application make sense.

#### Programme target: >1000x lower AI hardware cost, as a time/cost Pareto frontier against MLPerf baselines

- Plain: ARIA's Scaling Compute programme sets a headline of dropping the hardware cost of training large AI models by more than 1000x, shown as a target time-versus-total-cost curve against published MLPerf results. Cost is operational plus capital cost, estimated by creators and checked by an independent test and evaluation team.

> "It is possible to drop the hardware costs required to train large AI models by >1000x" ; "we show the targeted time/cost pareto frontier to train three specific workloads from the MLPerf benchmark (to the quality level described in the benchmark)" ; "Total Cost = (Operational Cost + Capital Cost) = £4.4M" for MLPerf entry "3.1-2057 GPT Nvidia H100-SXM5-80GB 512 GPUs 58.3 min" ; "The models and cost estimates will be re-evaluated by the T&E team every six months"

- URL: https://www.aria.org.uk/media/22ehvylu/aria-scaling-compute-call-for-proposals.pdf (Section 1, Figure 2; Section 3 Cost Estimations)

- Stated conditions: About training large AI models (GPT3-large, Stable Diffusion-medium, ResNet-50-small) 'to the quality level described in the benchmark'. Capital costs are admitted to be partly excluded: 'many capital expenditures are NOT included in this cost calculation (switch ASICs, optical cables, cooling, etc..), leading to an underestimate'. Teams must justify estimates 'with the understanding that these estimates contain many assumptions'.

#### System-level compute efficiency in TOPS/W with bandwidth density in TB/cm2, and a 'better than best known alternative' target form

- Plain: For matrix multiplication ARIA plots the target as TOPS per watt against terabytes per square centimetre and insists the efficiency number is measured for the whole system. For matrix inversion it states the target as a ratio against the best known alternative (time and energy) at a stated accuracy.

> "Note that the 'Compute Efficiency' metric below must describe the measurement at the system-level (not simply the arithmetic efficiency)." ; "approximately compute (to within 1% accuracy) the inverse of random, positive semi-definite matrices. These computations must be accomplished in 10x less time and 1000x lower energy than the best known alternative." ; thesis: "The energy/time requirements for these workloads are governed not just by the mathematical operations but also the resources required to get information to/from memory and to other processors."

- URL: https://www.aria.org.uk/media/22ehvylu/aria-scaling-compute-call-for-proposals.pdf (Section 3, TA1.1 and TA1.2, Figure 4) ; https://www.aria.org.uk/media/mcgn0i55/aria-unlocking-ai-compute-hardware_accessible.pdf (What we expect to fund)

- Stated conditions: Figure 4's axes are TB/cm2 (about 1e-5 to 10) and TOPS/W (1 to 100000); the target star sits near 1 TB/cm2 and about 1e4 TOPS/W, read by eye from the chart image, not from text; the thesis figure 2 uses 'the assumption that the operations are int8 number format'. TA1 building blocks 'should be manufacturable using existing CMOS processing facilities'.

#### Charting the Course: system-level software simulation of performance, power and cost

- Plain: ARIA funds simulators that predict the performance, power and cost of any combination of algorithm, hardware and system scale, so that bottlenecks can be seen before building. Its thesis update says systems-level analysis is undervalued and that economics should act as constraints.

> "develop software simulators to help the research community map the expected performance/power/cost for any future combination of algorithm, hardware, componentry, and system scale. The goal is to quantify the bottlenecks from different components in the stack" ; "If we use the building blocks to build a fully functional system at scale, how well will it work and how much would it cost?" ; "Systems-level analysis is highly undervalued."

- URL: https://www.aria.org.uk/opportunity-spaces/nature-inspired-computation/scaling-compute/funded-projects ; https://www.aria.org.uk/media/22ehvylu/aria-scaling-compute-call-for-proposals.pdf (TA3) ; thesis 'UPDATE: OUR THINKING, EVOLVED'

- Stated conditions: Aimed at novel hardware modalities and large-scale AI training/inference systems. The funded Imec project assumes 'a heterogeneous mix of logic, memory and interconnect technology options'.

#### Precision tolerance of AI workloads

- Plain: ARIA's thesis argues that low-precision computation is acceptable for AI, citing work that showed 4-bit quantised transformers can run efficiently. It names AI's tolerance to noise and reduced precision as why AI is the focal workload.

> "the digital AI accelerator community has recently shown that high levels of precision may not be necessary [5], raising the opportunity to challenge convention" and "AI workloads provide a compelling focal point due to their tolerance to the tenets listed above"

- URL: https://www.aria.org.uk/media/mcgn0i55/aria-unlocking-ai-compute-hardware_accessible.pdf (Why this programme; What we expect to fund)

- Stated conditions: Stated for large AI accelerators and analog/mixed-signal in-memory compute; 'the caveat being that the precision of computation is limited'. The cited result [5] is Keller et al., 17-95.6 TOPS/W, per-vector 4-bit quantisation, in 5nm.

#### Heterogeneous orchestration as a hypothesis ARIA tests (Scaling Inference Lab, Cluster 2) versus Fractile's view that heterogeneity is transient

- Plain: ARIA's testbed has a cluster on mixing different accelerators under one orchestration layer for agentic workloads. Goodwin, in contrast, calls such heterogeneity a likely temporary response to chips that cannot do everything.

> ARIA: "By combining different accelerator architectures under a unified orchestration layer, the cluster tests whether intelligent workload distribution can optimise performance across mixed hardware environments." Goodwin: "Heterogeneity is is actually a really challenging thing. And I think it's a transient response to the fact that you don't today have a chip that can kind of do it all" and "I think there is a danger for anybody that is working, you know, purely in the software layer. ... a lot of that could collapse back down over time"

- URL: https://www.aria.org.uk/opportunity-spaces/nature-inspired-computation/scaling-compute/scaling-inference-lab (Cluster 2, technology partner Callosum) ; https://www.youtube.com/watch?v=UZ8eYaAf08M

- Stated conditions: Cluster 2 'tests whether'; it is a question, not a result. Goodwin's objection is about stranded capacity in data centres with a fixed mix of chips bought for years.

#### ARIA's definition of an AI Scientist and the loop it must close

- Plain: ARIA defines AI scientists as tools that automate the core end-to-end process of discovery, and requires the full loop from hypothesis to a written report that states which human actions helped. The call wants an already working system, an easy problem it can solve and a harder one where it may struggle.

> "AI scientists – AI tools that are designed to automate the core end-to-end process of science discovery" ; "We are specifically looking for AI systems that are able to perform the full end-to-end workflow of scientific knowledge creation. This includes: Ideation and hypothesis creation; The design of experiments to test the hypothesis; The ability to run experiments in (ideally fully automated) labs, and; Interpretation of the results and the drawing of conclusions. The AI system should be able to place the work in the context of related literature and knowledge, and produce a written report describing related work, the idea explored, experiments, results and conclusions. The report should also include clear and unambiguous acknowledgement of what roles or actions any human has performed in the process to assist."

- URL: https://aria.org.uk/media/za3mj5h1/ai-scientist-solicitation-call-document_accessible.pdf (Introduction; Scope, pp.2-3)

- Stated conditions: Needs 'an already functioning AI Scientist system', 'this is NOT directly a call to fund the development of an AI Scientist system'. Loop on the AI in Science pages: "generate hypotheses, design experiments, run them in automated labs, interpret results, and iterate on findings" and 'designed to conduct the entire research process without continuous human intervention' (https://aria.org.uk/ai-in-science/ai-scientists). Funded projects are physical-science problems; the call: "(ideally) execute the experiment on physical hardware (e.g. an automated or semi-automated labs)".

#### AI Scientist selection criteria and two-problem structure

- Plain: ARIA scores proposals on evidence of capability and how much of the workflow is automated without human intervention, on problem ambition and clarity, on what ARIA learns, and on transparent cost. Each project states a base problem and a harder extension problem so limits are visible.

> "AI Scientist System Capability & Automation: Evidence of the AI system's ability to perform the proposed work and the extent of end-to-end automation of the scientific workflow without human intervention." ; "Each proposal should present two distinct problems: a base problem that the teams are confident their AI Scientist system can solve, and a more challenging extension problem that the system may struggle to solve." ; "a transparent pricing breakdown with no hidden costs"

- URL: https://aria.org.uk/media/za3mj5h1/ai-scientist-solicitation-call-document_accessible.pdf (Guidance; How we'll choose the projects)

- Stated conditions: Call closed 14 Nov 2025; 245 applications, 12 projects funded, 'nine-month sprints' (https://aria.org.uk/ai-in-science/ai-scientists).

#### Albert: ARIA's AI Scientist harness, static-baseline check, score-per-minute efficiency and benchmark hygiene

- Plain: ARIA built a small multi-agent AI scientist (Explorer, Theorist, Director, Technician, Chronicler) and tested it on hidden-rule virtual worlds and a 40-compound material optimisation with an experiment cost. It reports score divided by execution time, compares against a hand-built optimiser, and sandboxes runs so agents cannot read earlier runs.

> "If we look at the score achieved divided by the total execution time we get a metric of efficiency, the score per minute of execution time" ; "The 'Static' baseline is not an AI Scientist loop. It is a hand-built optimizer using the same hidden simulator interface, included as a sanity check. If an agentic system cannot approach a straightforward optimizer on this kind of task, that tells us something about the overhead of autonomy" ; "The final score combines material quality with an experiment-cost penalty after the first 15 experiments." ; "AI Scientist benchmarks need the same kind of hygiene as wet-lab protocols: clean separation between trials, explicit rules about what information is available, and audit trails showing which observations came from which experiment."

- URL: https://aria.org.uk/insights/2026/can-an-ai-scientist-really-discover-knowledge (Albert Architecture; The Efficiency Metric; Purpose of the Static Baseline; Emergent Shortcut-Seeking)

- Stated conditions: Mocked instruments in virtual worlds: "These are virtual worlds, not real wet labs, and the results test scientific search behaviour under controlled hidden rules rather than end-to-end real-world discovery." Alloy: 50 runs per configuration, noisy readouts scored against the noiseless simulator. Only Gemini and GPT families tested. The efficiency metric is "not the same as financial cost".

### Where it applies in our pipeline

#### 1. ARIA's AI Scientist definition and loop (hypothesis, experiment design, run, interpret, report, iterate, human roles stated)

- Where: Whole pipeline, as one slide and as a section in the final report: (1) prompt, critical questions, clinician bar and the spec = problem framing and hypothesis; (2) agents propose many small designs per round = ideation; (3) batch fine-tune of 256 candidates = experiments run; (4)-(5) synthesis, bit-for-bit check of 3,880 of 3,880 windows and the formal equivalence proof = interpretation and conclusions checked; (6) report; next round = iterate.

- Already exists: Mostly yes: the loop exists end to end, runs rounds, and writes a report. Naming it and showing the stage-to-definition mapping is enough for most of it. Two honest gaps against their text: the experiments are in silico (ARIA says 'ideally fully automated labs', and its funded projects are physical), and the report must 'place the work in the context of related literature' and 'acknowledge what roles or actions any human has performed'.

- To build, and the number to report: (a) A short 'who did what' ledger auto-written into the report: human actions (prompt, answers to critical questions, clinician bar) versus agent actions (which model wrote the spec, which proposed designs, which wrote summaries), pulled from run logs; shown as a two-colour strip on the dashboard. (b) A 'base problem / stretch problem' pair in the demo: the base problem the system solves to the bar (3,880 of 3,880), and one stretch problem where it is expected to struggle (for example a tighter clinician bar or a smaller gate budget) with the honest result, including a failed round and how the next round responded. (c) One line of related-work in the report (the reference model's source), if not present. Number reported: share of pipeline steps run without a human action, counted from the ledger.

- Sentence for the demo: We mapped our pipeline onto the AI Scientist loop that ARIA's call describes: hypothesis, experiment design, running, interpretation, report. Our experiments are in silico, not in a wet lab, and our report states which steps a human did.

- Why their people would accept it: It uses their own definition verbatim, keeps the required human-role acknowledgement and the base-versus-stretch honesty, and says plainly the lab is simulated.

#### 2. Static baseline, score per minute and experiment-cost accounting (from ARIA's Albert write-up) for the speedup claim

- Where: Stage 3 (batch fine-tune of candidates) and the search over designs in stage 2, for the judged 'speedup against a credible baseline'.

- Already exists: Partly: the product measures 256 candidates per batch at 1,626 per minute. What is missing is a baseline run next to it.

- To build, and the number to report: By Sunday midday: a baseline script that does the same search the plain way on the same GPU: candidates fine-tuned one at a time (same data, same epochs, same bar), and a hand-built non-agent search (random or grid search over the same design space with the same experiment budget), both run on the same reference model. Dashboard: a table of candidates per minute, wall-clock minutes and number of candidate trainings needed to first reach the clinician bar, plus cost per run (GPU minutes and model-API tokens) because ARIA wants 'a transparent pricing breakdown'. Report: speedup = baseline minutes to reach the bar divided by ours, measured on the same hardware, with both runs' seeds and the batch size shown. If the agent loop does not beat the static search, say so, as ARIA does.

- Sentence for the demo: Following ARIA's AI Scientist write-up, we report a score-per-minute figure and run the same search with a plain hand-built baseline on the same GPU, so the speedup is against a credible baseline.

- Why their people would accept it: It copies ARIA's own sanity check (a static optimiser as baseline) and reports a loss honestly if it happens, which is exactly the habit their write-up praises.

#### 3. Memory-wall quantity: weight bytes moved per inference, with the chip as the extreme end of 'load the weights every time'

- Where: Stage 4 and 5 output: the netlist compared with the reference model it was compiled from.

- Already exists: Yes by construction: weights are wired into gates, so the chip has no weight memory to read. It has not been stated as a number.

- To build, and the number to report: Two numbers on the report page, both countable by script: (a) bytes of weights the reference model must load per inference (parameter count times bits per weight divided by 8, from the model file) against (b) memory macros and RAM or ROM cells in the synthesised netlist (expected 0; count from the Yosys stat output) and weight bytes fetched per inference from off-chip memory (0, since none exists). Show that next to 2,330 gates. If a number is an estimate, label it 'estimated'.

- Sentence for the demo: Fractile's argument is that generating each token means reloading the model's weights through limited memory bandwidth; our chip is a case where the weights are the wiring, so weight bytes fetched per inference is zero. We are naming the same quantity, not their method.

- Why their people would accept it: It uses their central quantity (weights loaded per output over a bandwidth-limited link) accurately and does not pretend their stacked-DRAM approach is ours.

#### 4. Amdahl's law / theory of bottlenecks (Goodwin) for 'reshape the problem to expose parallelism'

- Where: Whole pipeline timeline: serial parts (language-model spec writing, critical questions, Yosys synthesis of the single best candidate, formal proof) versus the parallel parts (256-candidate GPU batch, layouts in parallel containers).

- Already exists: The reshaping is done (thousands of candidates as one GPU batch, layouts in parallel). Not yet shown: where the time goes after the speedup.

- To build, and the number to report: Instrument wall-clock per stage (timestamps in the run log), draw a stacked bar of one run, and compute the Amdahl bound: with serial fraction s measured from the log, the best possible speedup from more parallelism is 1/s. Dashboard number: measured end-to-end time, serial fraction, and the bound. Also report that the next bottleneck is now the biggest serial stage (say, formal proof or synthesis).

- Sentence for the demo: Goodwin's point is that once you parallelise what you can, the part you cannot parallelise sets the pace; here is our measured serial fraction and what it caps.

- Why their people would accept it: It uses Amdahl's law the way Goodwin does, to say where the next limit is, and does not overclaim an unbounded speedup.

#### 5. Approximate fast search, then a trusted final check (the 'fuzzy placement then DRC/LVS sign-off' pattern)

- Where: Stages 3 to 5: cheap approximate scoring of thousands of candidates, then exact verification only for the best.

- Already exists: Yes: batch fine-tune ranks thousands cheaply; only the winner is synthesised, checked bit for bit, and proven equivalent.

- To build, and the number to report: Show the funnel on the dashboard: thousands of candidates, top few synthesised, one verified. Report the cost per stage and that exact checks ran on 100% of shipped output. Do not call Yosys plus equivalence 'sign-off' in the foundry sense.

- Sentence for the demo: We follow the pattern Goodwin describes for chip design: iterate fast with approximations, then rely on an exact check at the end; ours is bit-for-bit verification and a formal equivalence proof.

- Why their people would accept it: It is the same division of labour he describes, and we state that our check is functional equivalence, not foundry sign-off.

#### 6. Time/cost Pareto frontier and 'better than the best known alternative' reporting

- Where: Output of stages 3 to 6: candidates versus accuracy against the clinician bar, with the smallest passing chip highlighted.

- Already exists: The selection of the smallest chip that meets the bar is the product's job; the scatter of all candidates is not shown.

- To build, and the number to report: A scatter plot: x = gate count or parameter bits, y = clinician-bar metric, thousands of dots, frontier line, and the chosen chip. If gate counts exist only for the best chip, synthesise the top 10 to 20 frontier candidates in parallel containers (already available) so the frontier is real, and label the others 'proxy: parameter bits'. Add a baseline row for the reference model on a general-purpose CPU: latency per window and software model size. Report in ARIA's form: 'X times fewer ... than the best known alternative', with the alternative named and measured.

- Sentence for the demo: We plot design cost against quality as a Pareto frontier, the way ARIA frames its targets, and report the chip against a named baseline.

- Why their people would accept it: Both organisations speak in Pareto frontiers and baselines; ours is a real measured frontier rather than a slogan.

#### 7. System-level reporting in ARIA units (energy per inference, TOPS/W) with the target shown only as context

- Where: Stage 4 to 6 report.

- Already exists: No energy figure exists; 2,330 gates is measured.

- To build, and the number to report: A power estimate: simulate the 3,880 test windows on the netlist to get switching activity, then estimate energy per inference with an open-source power tool on the synthesised netlist (or the layout if time), labelled 'estimated, pre-silicon, technology library X'. Report energy per inference, inferences per second, operations per inference, and so TOPS/W at the whole-chip level. Put ARIA's frontier (the Figure 4 axes) as a context line only; do not plot the chip against a 1e4 TOPS/W target.

- Sentence for the demo: We report energy per inference and operations per watt at the whole-chip level, the system-level way ARIA asks for, as an estimate before silicon.

- Why their people would accept it: It respects their 'system level, not just arithmetic efficiency' rule and labels estimates as estimates.

#### 8. Parallel agents plus a sequential refinement loop (test-time compute scaling) for the design search

- Where: Stage 2: agents propose many small designs per round; rounds are sequential.

- Already exists: Yes: many designs per round, several rounds, different models for different jobs.

- To build, and the number to report: Optional: a chart of best score versus round and versus number of candidates, showing what parallel breadth buys and what extra rounds buy. Optionally a majority-vote check among proposals only if used.

- Sentence for the demo: Like Fractile's picture of many agents running in parallel with long sequential chains on top, our search is wide within a round and sequential across rounds.

- Why their people would accept it: It matches their 'two axes' picture; weaker than the others because their claim concerns LLM chains, not model design search.

### Do not

- Saying the chip uses or validates Fractile's approach. Their approach is to stack DRAM on logic for 'the bandwidth of SRAM, but with the capacity and the scalability of DRAM' (20VC). The product removes memory by wiring fixed weights into gates. Their own text does not say anything about wiring weights into gates; the jobs page lists a 'Foundry Engineer - DRAM' role, and Goodwin says they do not want to be 'the company that cracked 3D DRAM'.

- Reporting tokens per second or setting the product beside '~1,200 tokens per second'. That target is for 'generating many tens of millions of tokens' with very large LLMs 'at very long contexts' (manifesto). The product's chip classifies sensor windows; its only language-model output is run summaries.

- Claiming the product meets or approaches ARIA's >1000x cost target or the ~1e4 TOPS/W point. The programme is 'anchored around reducing the hardware costs required to train large-scale AI models' (call, Section 1), against MLPerf GPT3, Stable Diffusion and ResNet-50 training workloads, and the call says it will not fund 'Pure algorithmic advancements whose primary benefits can be realised using commercially-available hardware'.

- Describing the product as an ARIA AI Scientist, as ARIA-funded, or as responding to an ARIA programme for AI-designed chips. The call needs 'an already functioning AI Scientist system', is closed (deadline 14 Nov 2025), and funded 12 physical-science projects; the earlier notes record an ARIA AI-for-hardware-design programme as 'not found'. Use their definition as a mapping, not as a status.

- Calling the pipeline's in silico steps 'experiments in an automated lab'. ARIA says 'run experiments in (ideally fully automated) labs' and even its own Albert write-up says 'These are virtual worlds, not real wet labs'; say 'in silico' and state the human roles, which ARIA's report rule requires.

- Presenting the use of several kinds of hardware (GPU, CPU, containers) as something Fractile endorses. Goodwin calls heterogeneity 'a transient response to the fact that you don't today have a chip that can kind of do it all' and warns about 'stranded capacity'. ARIA's Cluster 2 only 'tests whether' orchestration across accelerators helps.

- Using Amdahl's law or 'speedup' without stating the serial fraction. Goodwin uses the law as a warning ('the part that I can't parallelize doesn't' get faster), and ARIA's Albert write-up says to read score and runtime together, not one alone.

- Calling Yosys synthesis plus equivalence proof 'sign-off' or 'tape-out ready'. Goodwin: the final sign-off is 'DRC and LVS clean' by foundry-approved tools, and tape-out is 'a seminal handoff'. The product's checks are functional equivalence and bit-for-bit tests.

- Presenting a chip built for one model as Fractile-style specialisation without the condition. Goodwin's chip has to serve a stable, huge workload for 'a 3 to 5 year amortization window'; a per-device chip with fixed weights has no such stated condition, and Goodwin says specialisation weakens if 'the long tail ... was also a fat tail'.

- Comparing the product's score with the Albert or Alloy benchmark numbers or implying the product ran on them. Those are hidden virtual worlds with Gemini and GPT models, 3 runs or 50 runs per configuration, and exact-rule or experiment-cost scoring.

- Quoting 'intelligence per megawatt' or 'tokens per megawatt' as a measured metric. They are spoken framings with no formula or published value; the manifesto gives no energy figure at all.

- Using Fractile's or ARIA's name or logo in the UI as a partner or endorser. The team's earlier note says use plain text only; both organisations' terms ask for permission for logos (not re-checked here).

### Their own open problems

- ARIA thesis, 'What we are still trying to figure out': "Are we projecting the right performance targets, and are we sure our targets (e.g. TOPS-W target above) represent a big enough step-change to where industry will be in 3-5 years time?" ; "What do we benchmark against, besides MLPerf?" ; "Do we have accurate estimates of costs at industrial scale?" (https://www.aria.org.uk/media/mcgn0i55/aria-unlocking-ai-compute-hardware_accessible.pdf). The product can speak to the baseline question: it reports a measured, named baseline.

- ARIA thesis: "Systems-level analysis is highly undervalued." and "hardware demonstrations and comparisons against digital alternatives have yet to be shown" (for analog matrix-inversion substrates). The product can show a real netlist compared against a digital alternative on the same task.

- ARIA CTO on AI Scientists: "Can current systems actually handle experimental failure and adaptive redesign? Do they need human intervention at key decision points? What's the real throughput on automated equipment versus what's theoretically possible?" and "Can they iterate when things fail?" (https://aria.org.uk/insights/2025/why-we-re-exploring-ai-scientists-update-1). The product can show a failed round and the redesign, the human-action ledger, and measured throughput (1,626 candidates per minute).

- ARIA CTO: "Moving from 'this works in a demo' to 'this reliably produces novel insights' requires solving problems we don't fully understand yet." Same URL. The product can show repeatability across several seeded runs.

- ARIA AI in Science: "As AI systems make hypothesis generation increasingly abundant, the bottleneck in science is shifting toward validation: the physical capacity to test ideas in the real world." (https://aria.org.uk/ai-in-science/ai-scientists). The product's validation is bit-for-bit plus formal proof, and layout is the next physical step.

- ARIA Albert write-up: "In future versions, we would like to make the evaluation more structured, including penalties for false positives, uncertainty calibration, and evidence quality." and "A model that discovers three rules and invents two plausible but false ones may receive the same score as a model that discovers three rules and carefully refuses to overclaim." Also: "If models help generate the environments, have we accidentally made games that are rigged in the models' favour?" (https://aria.org.uk/insights/2026/can-an-ai-scientist-really-discover-knowledge). The product's verification (3,880 of 3,880 and a proof) is a check that does not reward overclaiming; it can state that test windows were held out.

- ARIA Albert write-up: "Are discrete tool calls the best way to interface LLMs with scientific instruments? ... Our early results suggest that this can sometimes be detrimental to model performance and can increase output variance." The product's agents hand work to batch code and Yosys rather than one tool call at a time; it can report that structure without claiming it answers the question.

- ARIA Albert write-up: "Code can help if the model writes a useful optimizer, but it can hurt if the model spends its budget debugging, overfitting noisy observations, or building infrastructure that is more complicated than the task requires." Same URL. Supports reporting the static baseline honestly.

- Goodwin (No Priors) on chip design: "there are still these loops in the middle of it that are kind of conventional solutions to NP-hard problems. ... layout tools that are doing place and route with conventional kind of uh algorithmic approaches which will run for days on end" and "could you have some kind of fuzzy placement algorithm in the meantime ... I think that is exactly where people should be should be doing more work because otherwise that is the bottleneck." (https://www.youtube.com/watch?v=OpeCP4wCxkA). The product's parallel layouts in containers is a small instance; report layout wall-clock.

- Goodwin (Forecast 2050): "the chip you actually end up making does still need to have a 3 year plus, you know, useful lifespan" and "I don't think we're yet going to be able to kind of change this paradigm of needing to build something that has a degree of of longevity to it." (https://www.youtube.com/watch?v=zPOyb4nCRRs). Honest limit for any single-purpose chip: a fixed-weight chip must be re-made when the model changes.

### Not read

- No Fractile technical paper, patent, arXiv paper or datasheet was found. Web searches for Fractile patents on Google Patents returned none assigned to Fractile; USPTO, UK IPO and Espacenet were not searched directly. Goodwin's X account (https://x.com/goodwin_ml) was not read. So 'not found': any Fractile figure for energy per operation, pJ per token, bytes moved per token, cost per token or price per unit of compute; the only numbers are the spoken ones quoted above (40 vs 1,200 tokens per second; flops x1,000,000 vs bandwidth x40; '25 times more bandwidth per chip than an HBM-based chip'; '10 to 100 times more bandwidth'; 'more than 10x advantage'). A 2024 claim of 100x faster and 10x cheaper appeared only in third-party coverage, which I did not use.

- The three podcast transcripts are YouTube auto-captions (the company is mis-spelled 'Fractal'; punctuation and some words may be wrong); they were not checked against audio. In the Forecast 2050 episode a large part (Sir Robin Saxby on Arm) was read but is not relevant. The manifesto gives a $220M raise (13 May 2026) while the 20VC captions say '$720 million Series C'; I did not resolve the difference and did not use either figure.

- Fractile's Join the mission (jobs) page was read only in its first ~80 lines, and the Legal notices page and the 20 individual role descriptions were not read. The Fractile press links (FT, WSJ, Fortune, Calcalist) were not read by design.

- ARIA thesis: the figures are images and the accessible PDF contains no text for them; I read Figure 4 (matrix multiplication target) and Figure 2 (cost curves) from the 2024 call document as page images, so the target near 1e4 TOPS/W and ~1 TB/cm2 is read by eye, not from text. Table 1 (matrix-inversion numbers, page 9) and Figure 5 (connectivity target, page 11) were not viewed. Of the 2024 call document I read lines 1-470 (Sections 1-5) and scanned the rest (eligibility, evaluation criteria, references) only by keyword. TA4 benchmarking RFP: read the first ~200 lines of 364; contract terms and the rest not read.

- ARIA has no separate 'programme thesis' for AI Scientists that I could find: the definition comes from the call document (v1.0, 14 Oct 2025), the AI in Science pages and the CTO's essays. Not read: the 12 funded AI Scientist project modals, 'Opportunity spaces: three years in', the downloadable Albert report PDF, the Decoding Science interview, the MIT Technology Review, BBC, Times and DDW articles (third-party), the CommonAI Lab website, the Callosum podcast, and the Vimeo videos for the Charting the Course projects and the programme presentation.

- Not checked: whether ARIA's or Fractile's terms allow the product to quote them in a demo (the earlier notes record logo and name rules; the fr-terms files in /tmp are from earlier work and were not re-read). Not checked: any detail of the product's own code, logs or dashboard, so every 'already done' above comes from the task description only; the to-build items (power estimate, baseline run, ledger, frontier plot) have not been tried.
