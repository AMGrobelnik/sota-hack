# What each supporter has made that we can use

Date: 2026-11-21. Sources are two research passes treated as data. Where they say "not confirmed", this note keeps that.

## Summary

- Callosum: the Tailored Inference API is its only product. Access today: no, docs sit behind sign-in and no key is confirmed. Ask: do hackathon teams get a key, and does it accept an OpenAI-style chat completions request with a base URL?
- Inherent Labs: paper on Faraday and Replica is public to read. Access today: paper only; code, data, weights and API not confirmed. Ask: is Faraday or any Replica task and judge available to teams today?
- Fractile: nothing Fractile-made and usable was found. Access today: none. Ask: is there a performance model, simulator or SDK we can run, and may we show its output?
- ARIA-funded teams: thermox (Normal Computing) and Vehicle are public open source. Access today: yes, pip and GitHub, no key. Ask: which Vehicle release and verifier works on an exported ONNX model, and what is its licence?
- Tinker: Inkling 2 Mini open weights and an OpenAI-compatible endpoint. Access today: weights public; hosted use needs a Tinker key. Ask: does the event credit allocation include a Tinker key, and where do we claim it?

## Callosum

### What is usable

- Tailored Inference API (the only product)
  - Access: Not public. The API docs at docs.callosum.com sit behind Google sign-in. The public pages give no sign-up, key process, pricing, endpoint or SDK. I did not sign in.
  - Terms: not confirmed. The notes file records that callosum.com/terms returned 404; the homepage links a Terms of Service page, which I did not read.
  - Url: https://docs.callosum.com
  - Quote: "Sign in to read this page."
- Docs introduction (public part)
  - Access: Public page, but the Quickstart, Capabilities, Models and a gpt-oss-120b page are all locked. A gpt-oss-20b page is listed as coming.
  - Terms: not confirmed
  - Url: https://docs.callosum.com/docs-app.js
  - Quote: "We provide tailored inference to your needs, dramatically reducing inference cost and unlocking new possibilities like ultra-fast inference through early Cerebras capacity, while keeping or exceeding frontier AI quality."
- Callosum GitHub, SDKs, open-source code, models, datasets
  - Access: None found. github.com/callosum is an unrelated personal account with no repos. The blog and homepage mention no SDK, OpenAI-compatible interface, API keys or open source.
  - Terms: not applicable
  - Url: https://callosum.com/blog
  - Quote: "Callosum doesn't have any public repositories yet."
- Paper: The Principle of Maximum Heterogeneity (blog post labelled Paper, 26 Feb 2026)
  - Access: Public to read. No code or data found. The team's notes say its maths was not read.
  - Terms: not confirmed
  - Url: https://callosum.com/blog/the-principle-of-maximum-heterogeneity
  - Quote: "entirely new accelerator designs running new model architectures"
- Hackathon offer from Callosum
  - Access: not confirmed. The Luma page mentions generic AI credits and GPU environments only, with no Callosum API or keys. The team's Discord digest says nothing was posted by Callosum, and the only sponsor content is a 12:00 to 12:30 Saturday talk.
  - Terms: not confirmed
  - Url: https://luma.com/scientific-parallelism
  - Quote: "supported by Callosum, Inherent Labs, ARIA and Fractile"

### Best integration

Nothing Callosum has made can be built in without a key, so the only integration that is real by Sunday midday depends on one answer at the event. If an organiser or Callosum person hands over an API key and base URL, the dashboard shows a third entry in the model picker, "Callosum Tailored Inference", next to "Claude CLI" and "OpenRouter". The run page labels each summary or agent call with the provider that served it. The backend change is small. The existing OpenRouter client in the Python backend gets a provider entry with a base URL and key from environment variables, and it works only if their request shape matches OpenAI chat completions, which is not confirmed. The calls to route through it are the clinician-facing run summary and the agent design proposals. Chip synthesis, fine-tuning and verification stay where they are. Show a real call with its response id and latency, and report which model Callosum picked only if the API returns it.

### Fallback

Add "Callosum Tailored Inference" to the model picker as a disabled option marked "available, not used in this run: no access key". Do not call it or fake a response. In the pitch, cite only their public thesis: "The next substantial leaps in AI capability, cost and speed will come from this heterogeneity." (https://callosum.com/blog/welcome-heterogeneous-intelligence). Say ChipIn takes that thesis to its end, with one chip made to fit one model. The team's own sponsor-wording note has the corrected line and the do-not-claim list.

### What would be a false claim

- ChipIn is built on, uses, partners with or is endorsed by Callosum, unless a real key is used in the run.
- Callosum designs chips or does chip synthesis. They partner with silicon companies, and the team's notes found nothing on chip design.
- Callosum does training or fine-tuning orchestration. The product pages describe inference only.
- ChipIn does heterogeneous runtime routing across chips. It runs on GPUs and outputs one gate-level chip.
- That Callosum's API is OpenAI-compatible, has a public model list or pricing, or gives hackathon keys. None of that is confirmed.
- The 3.7x faster claim, reported by a news outlet as Callosum's own figure, as a result ChipIn measured.
- Using the Callosum logo. No logo or name rule was found, so use plain text only, or ask press@callosum.com.

### Question to ask at the event

Do hackathon teams get a Callosum API key for Tailored Inference, and does it accept an OpenAI-style chat completions request with a base URL?

### Event offer

The Luma page and the team's notes show no Callosum-specific offer. The Luma page says only generic "AI credits" and "GPU environments". Callosum gives a talk on Saturday from 12:00 to 12:30. The Discord digest says no Callosum office hours or on-site people are named. Credits arrive through the organisers, and the notes say "ask organizers", so a Callosum key is not confirmed.

### Not confirmed

- Whether Callosum provides keys to hackathon participants.
- The request shape, base URL, OpenAI or OpenRouter compatibility, and whether streaming is supported.
- The model list. Only gpt-oss-120b has a page in the docs navigation, and it is locked, with gpt-oss-20b listed as coming.
- Pricing and rate limits.
- The licence or terms of use. The terms URL was not read, and an earlier note says callosum.com/terms returned 404.
- Any open-source code, SDK or datasets from Callosum.
- Callosum's offer at this event. The sponsor talk content was not read.
- How the earlier request about Tinker and inkling2 relates to Callosum. Tinker is not Callosum's product and I did not research it.

## Inherent Labs

### What is usable

- Paper: Training AI Scientists to Replicate Research (describes Faraday, a 27B AI-scientist agent, and Replica, a 310-task paper-replication task space with an auto-generated rubric judge). Reading only; no artifact released.
  - Access: Public (paper only)
  - Terms: Only licence found is arXiv's non-exclusive distribution licence, which covers the paper, not code or models
  - Url: https://arxiv.org/abs/2608.13331
  - Quote: "Replica, a scalable task space for paper replication"
- Faraday (27B agent) and Replica (310 tasks from 100 papers, per-task rubric judge). Described on the site; code, data, weights and API not confirmed as released.
  - Access: Not confirmed. No public download or API found. The paper's only route is an invitation to email.
  - Terms: Not confirmed; no licence stated
  - Url: https://inherentlabs.ai/research/training-to-replicate
  - Quote: "310 tasks from 100 ML and AI-for-science papers"
- Contact route for access to Faraday, from the paper's Community engagement section.
  - Access: Email, by invitation (not a sign-up). The team must not email from here.
  - Terms: Not confirmed
  - Url: https://arxiv.org/html/2608.13331
  - Quote: "we would be delighted to hear from you at faraday@inherentlaboratories.com"
- Event offers from Inherent: a talk at 12:00 to 12:30 Saturday and an offer to post the paper link. No credits, API or challenge from Inherent found. The Luma page's only credits line is generic and not attributed to any supporter.
  - Access: Talk only. Credits are from organisers.
  - Terms: Not confirmed
  - Url: context/adrian-notes/2026-11-21-opening-talk.md and https://luma.com/scientific-parallelism
  - Quote: "Speaker offered to post the link; covers the 27B model results and training methodology. / "We'll have access to GPU environments, AI credits, and experienced mentors and advisors.""
- Inherent's homepage lists no GitHub, Hugging Face, API or dataset. Research index has one item only. The GitHub org inherent-labs exists but is empty; the notes do not confirm it is theirs.
  - Access: Nothing public to use
  - Terms: Not confirmed. /terms returned 404 per the team's wording-check note.
  - Url: https://inherentlabs.ai/research/
  - Quote: "This organization has no public repositories. (https://github.com/inherent-labs)"

### Best integration

Nothing of Inherent's can be called today, so the honest integration is a replication-style check on our own side, in Replica's own terms, with no Inherent code or model involved. (a) Dashboard: add a "Replicate first" stage before shrinking. The user picks a published seizure-detection baseline (a small public EEG model, for example on a public EEG seizure set), and the run shows a "Replication check" card: paper-reported metric vs our reproduced metric, a pass/fail band, then the shrink starts only from a replicated baseline. Label it "Replication check, inspired by the Replica paper idea (arXiv 2608.13331). Not Replica, not Faraday, not run by Inherent." (b) Code: replicate.py takes a baseline spec (YAML: dataset, model, reported sensitivity and false-alarm rate, tolerance). It calls the existing agent backend (the Claude CLI or an OpenRouter model) to write or fix the training script, runs the existing GPU batch trainer on it, and compares the result against the reported number. The dashboard reads the JSON result. Build the check against a baseline whose numbers the team can verify itself. If Inherent grants access to Faraday or Replica tasks, the same agent-backend slot takes it as one more model-picker entry. Do not describe this as using Inherent's work unless that access is confirmed.

### Fallback

In the model picker, add one disabled row: "Faraday (Inherent Labs): available in principle, not used in this run" with the tooltip "Described in arXiv 2608.13331; no public access found; not tested here." It stays greyed, makes no calls, and appears in no results table. The landing page names Inherent in plain text only, as an event supporter, with the corrected line from the team's wording-check note. No logo.

### What would be a false claim

- That ChipIn uses, runs on, is powered by, partners with or is endorsed by Inherent, Faraday or Replica (the relationship is event support only).
- That Faraday or Replica appears in the model picker as a working option, or that any result was scored on Replica.
- That Faraday is open, available through an API, or downloadable (not confirmed; the paper gives only an email contact). The Sunday notes call it an 'open model (Qwen)', but I found no source for that. Do not repeat it.
- That Faraday beats Claude Opus 4.8 or GPT-5.5 at chip design or anything beyond paper replication; the claim is their own, on their own benchmark and judge, for ML and AI-for-science papers.
- That Inherent works on chips, hardware, EEG or medical devices. Its homepage says AI can speed up hardware infrastructure and GPU kernels, but no such work is published.
- That our replication check is Replica or uses Inherent's judge. Call it our own check.
- Using the Inherent name as a logo, or implying they back the prize or the product.

### Question to ask at the event

Is Faraday, or any Replica task and its judge, available to hackathon teams today, by API, weights or task files, and if so what is the access route and the terms?

### Event offer

From the team's notes: Inherent gave a talk (12:00 to 12:30 Saturday) and offered to post the paper link. The notes record no credits, API, challenge, office hours or named on-site person from Inherent, and the Discord digest says Inherent has posted nothing. The Luma page says only "supported by Callosum, Inherent Labs, ARIA and Fractile" and mentions generic GPU environments and AI credits, which are not attributed to any supporter.

### Not confirmed

- Any public code, weights, API, dataset, Replica task files or judge from Inherent
- Any licence or terms for Faraday or Replica
- That the GitHub org inherent-labs belongs to Inherent Labs
- Release statements in the paper's appendices. Only the first 100,000 of 196,570 characters of the HTML were read, and the PDF text was not readable.
- Any Inherent credits, API, challenge or office hours at this event
- Faraday being a Qwen-based open model (stated in the team's notes, but no source found here)
- Any Inherent work on chips, hardware, EEG or medical devices

## Fractile

### What is usable

- Nothing Fractile-authored and usable by an outside team was found: no simulator, performance model, SDK, benchmark, paper, dataset or model page, no docs site.
  - Access: Not available. Public site has only manifesto, How we think, Jobs, Legal.
  - Terms: Terms of Use: name and logo are trade marks; use needs prior written approval (taken from the team's sponsor-wording-check note, not re-fetched).
  - Url: https://fractile.com/
  - Quote: "There are no docs, blog, GitHub, or developer-access links. (fetch summary of fractile.com home; page's own words: "Building hardware to advance AI's underlying capabilities and push the frontier forward.")"
- GitHub organisation fractile-ai (linked from fractile.com's GitHub profile field as www.fractile.ai): three public repos, all forks of other people's projects (SpinQuant, stablehlo, llvm-project), last pushed Jan to Feb 2025. Not Fractile-made tools; no Fractile code in them was confirmed.
  - Access: Public
  - Terms: stablehlo: Apache-2.0. SpinQuant and llvm-project: GitHub API reports NOASSERTION (upstream SpinQuant licence not checked, so not confirmed; do not assume it is permissive).
  - Url: https://github.com/fractile-ai
  - Quote: "llvm-project true NOASSERTION; stablehlo true Apache-2.0; SpinQuant true NOASSERTION (gh api orgs/fractile-ai/repos, fork=true for all three)"
- A QEMU-based functional simulator of Fractile's accelerator exists internally, per a job posting and a third-party report. Nothing says it is public.
  - Access: Not public (not confirmed either way)
  - Terms: not confirmed
  - Url: https://globaltalentjobs.technation.io/companies/fractile/jobs/75181430-senior-simulation-engineer
  - Quote: "Search summary: the posting says the company is developing a QEMU-based functional simulator of its AI acceleration hardware. (secondary: https://sacra.com/c/fractile/ says developer tooling including a QEMU-based simulator lets teams start before silicon arrives)"
- Published numbers usable only as stated company claims or thesis, not as benchmarks: the founder's manifesto sentences, and a target of about 1,200 tokens per second. CEO's 25x bandwidth per chip vs HBM claim is from a podcast; no independent audit.
  - Access: Public text
  - Terms: not stated; trade-mark rule applies to name and logo
  - Url: https://fractile.com/manifesto
  - Quote: ""The technical and economic limits on inference speed, above all from memory bandwidth that has failed to scale on current architectures, are what is constraining progress." (via team note 2026-11-21-sponsor-wording-check.md)"
- Event offer from the supporters in general (GPU environments, AI credits, mentors). Not attributed to Fractile. Two Fractile staff present, and Clara available to help.
  - Access: Event
  - Terms: not confirmed for Fractile
  - Url: https://luma.com/scientific-parallelism
  - Quote: ""We'll have access to GPU environments, AI credits, and experienced mentors and advisors" ; notes: "2 Fractal team members present; Clara available on the day to help participants" (adrian-notes/2026-11-21-opening-talk.md)"

### Best integration

Honest answer: there is nothing of Fractile's to call, so the best buildable item uses their thesis as the comparison metric, computed from ChipIn's own measurements, with no Fractile data. Dashboard: next to the winning chip, a card "Weight bytes fetched per inference". Row 1, a GPU or microcontroller running the same model: parameter count times bits per weight, read from the trained candidate's checkpoint. Row 2, the ChipIn netlist: 0 bytes of weight memory fetched, because the weights are wired into gates (the Yosys report shows no memory cells). Code: backend function weight_bytes(checkpoint, bits) reads the winner's quantised tensors; a Yosys stat parse confirms zero memory macros; the dashboard renders both numbers and the gate count and area from the same report. Frame it as "the cost Fractile says limits inference, measured on this model", without saying Fractile does or endorses this. Buildable by Sunday midday; needs only existing pieces. If Fractile staff at the event hand over any real number or tool, add it as a third row marked as theirs with their quote.

### Fallback

Add an entry to the machine picker: \"Fractile accelerator: available, not used in this run\" (greyed, no run button, tooltip \"no public simulator or SDK; not tested\"). Do not display any Fractile speed or cost figure as a result. Name as plain text only, no logo.

### What would be a false claim

- That ChipIn runs on, targets, compiles to, or was tested on a Fractile chip or simulator (none is public).
- That Fractile uses, endorses, partners with or favours weights-in-gates, or that their chip is hardwired or has no memory.
- Calling Fractile a sponsor or partner: the Luma page says only "supported by".
- Quoting Fractile's up to 100x faster / 10x cheaper or 25x bandwidth as verified: company statements, no independent benchmark; silicon is reportedly only simulated and the first commercial chip is not before 2027.
- Using the fractile-ai GitHub forks (SpinQuant, stablehlo, llvm-project) as 'Fractile's tools': they are forks of Meta, OpenXLA and LLVM code.
- Saying 'in-memory compute' is their thesis (only third-party reports use that phrase) or claiming kinship with their LLM and long-context focus.
- Using the Fractile logo without written approval (hello@fractile.ai).

### Question to ask at the event

Does Fractile have anything an outside team can run today, such as a performance model, simulator or SDK, that could estimate how a small fixed model runs on your chip, and may we show its output?

### Event offer

Luma lists GPU environments, AI credits and mentors without saying who provides them. Notes record two Fractile staff on site and Clara available to help. No Fractile-specific credits or hardware access are confirmed.

### Not confirmed

- Whether Fractile's QEMU simulator or any SDK is available to outsiders
- Any Fractile-provided credits, hardware or software at this event
- Upstream licence terms of the SpinQuant and llvm-project forks
- Contents of Walter Goodwin's May 2026 essay 'The future of AI scaling' (listed on the How we think page, not found or read)
- Any independent benchmark or measured silicon result from Fractile

## ARIA-funded teams

### What is usable

- thermox, Normal Computing's open-source JAX simulator of thermodynamic linear algebra (solve, inv, expm). Normal's ARIA-funded work is the CN101 thermodynamic chip.
  - Access: Public, no key. pip package thermox 0.0.6 on PyPI; GitHub normal-computing/thermox. The CN101 chip itself: no outside access confirmed.
  - Terms: Apache-2.0 (GitHub page and PyPI metadata).
  - Url: https://github.com/normal-computing/thermox
  - Quote: ""This package provides a very simple interface to exactly simulate" (GitHub); ARIA: "The Thermodynamic Matrix Inversion project, funded through our Scaling Compute programme" (https://aria.org.uk/insights/developing-a-world-first-thermodynamic-computing-chip)"
- Vehicle, a language and tool that embeds logical specifications into neural networks, compiles them to training loss and to verifier queries (VNNLIB solvers, Marabou; ONNX, TensorFlow, PyTorch listed). Made by the Southampton/Heriot-Watt/Strathclyde group of the ARIA Safeguarded AI project 'Quantitative Predicate Logic as a Foundation for Verified ML'. That Vehicle itself was paid for by ARIA is NOT confirmed (the repo page does not mention ARIA).
  - Access: Public. pip package vehicle-lang 0.29.0 on PyPI; GitHub vehicle-lang/vehicle.
  - Terms: Licence not confirmed (PyPI field empty, GitHub page did not name it). Docs: no stable version yet.
  - Url: https://github.com/vehicle-lang/vehicle
  - Quote: ""Vehicle is a system for embedding logical specifications into neural networks." Docs: "This project is under active development and no stable version yet exists." ARIA project listing: "Quantitative Predicate Logic as a Foundation for Verified ML", Ekaterina Komendantskaya + Robert Atkey (https://aria.org.uk/opportunity-spaces/mathematics-for-safe-ai/safeguarded-ai/funded-projects)"
- Scaling Inference Lab, run by CommonAI CIC with ARIA: an open testbed for rack-level AI hardware (pipeline parallelism on commodity/older GPUs, mixed accelerators, optical switching). Useful as a place to ask for compute, not as software.
  - Access: Not confirmed for outside teams or this event.
  - Terms: not confirmed
  - Url: https://aria.org.uk/insights/scaling-compute-from-new-chips-to-working-systems
  - Quote: ""an open testbed where new AI technologies can be inserted into rack-level systems""
- Nothing else released and usable was confirmed from ARIA's funded-project pages: Scaling Compute simulators (Imperial/Edinburgh/Cambridge; imec) list no release; the Precision Neurotechnologies funded-projects page lists no dataset or EEG tool; the AI Scientist cohort page (Liverpool, Lila, etc.) names no usable tool in what I could read.
  - Access: not confirmed
  - Terms: not confirmed
  - Url: https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects
  - Quote: "Page fetched: it "doesn't mention EEG or any EEG-based team" and no datasets or open-source tools (my reading of the page; no verbatim quote available)."

### Best integration

Vehicle as a pre-compile property check on the winning model, shown next to the bit-exact netlist check. Dashboard: on the winner card, a third badge 'Property: alarm does not flip under +/-e noise on the input window', with status verified / counterexample found, and the counterexample EEG window plotted when it fails. Code: (1) write seizure_robustness.vcl (a short Vehicle spec: for any window x within e of a reference window, |f(x)-f(ref)| < delta, on a handful of held-out reference windows); (2) after the winner is chosen, the backend exports the float model to ONNX (torch.onnx.export); (3) a new Python module chip/vehicle_check.py shells out to the vehicle CLI with --verifier Marabou (or loads the compiled VNNLIB query) and parses the verdict; (4) the dashboard API adds the verdict field to the run record. Scope it honestly: it checks the floating-point model, not the netlist, which the existing bit-exact equivalence ties to the quantised model; keep the model tiny so Marabou finishes. Risk: Vehicle has no stable version and the Marabou install may eat the morning, so time-box it to 2 hours; if the check does not run by Saturday night, use the fallback. thermox has no honest place in a gate-level chip flow, so do not force it.

### Fallback

Add an entry to the dashboard (a 'Verification tools' list beside the model and machine pickers): 'Vehicle (neural-network specification and verification) - available, not used in this run', greyed out, with a note 'not run; planned property: input-noise robustness'. No badge, no verdict, no ARIA logo, no claim that it ran.

### What would be a false claim

- That ARIA funds ChipIn, or that ARIA or Normal Computing gave the team credits or access (the event page only names ARIA a supporter and a prize demo slot).
- That Vehicle was funded by ARIA (only the group's related Safeguarded AI project is confirmed), or that Vehicle is stable or has a named licence.
- That the chip netlist is 'formally verified by Vehicle' - Vehicle would check the float model; the bit-exact equivalence is the netlist check.
- That the design uses Normal Computing's thermodynamic chip, or that thermox is in the pipeline, or that CN101 is open or accessible.
- Any claim of an ARIA-funded EEG dataset or benchmark: none was found.
- Anything about the Scaling Inference Lab hosting the runs.

### Question to ask at the event

Is anyone here from the Southampton/Heriot-Watt Vehicle team, or can ARIA staff introduce us: which Vehicle release and verifier (Marabou) works on an exported ONNX model, and what is its licence?

### Event offer

Only ARIA offer confirmed: the first prize includes a demo slot at ARIA's AI for Science Summit, Manchester, 26 Nov (luma page: \"a demo slot at ARIA's 2026 AI for Science Summit\"; notes: 2026-11-21-whatsapp-group.md and past-events.md). The page names ARIA a supporter without saying what it provides; credits, GPU environments and mentors are not attributed to ARIA. The team's notes show ARIA, Callosum, Inherent and Fractile have posted nothing on Discord (2026-11-21-discord-digest.md: \"Fractile, Callosum, Inherent Labs and ARIA have posted nothing\"), and ARIA gives no sponsor talk in the schedule. Nothing in the notes mentions Inkling, and I did not find Tinker linked to ARIA; Tinker credits appear as an open question in the discord digest.

### Not confirmed

- Whether ARIA funded Vehicle itself
- Vehicle's licence
- Signaloid open-source release or GitHub (fetch failed; funding is confirmed on the ARIA Scaling Compute listing)
- Marian Verhelst / KU Leuven MICAS (ZigZag, Stream, SNAX, Apache-2.0 for some repos) as ARIA-funded: ARIA's creators page did not list them, so I left them out of the list; an ARIA insight called her a Scaling Compute Creator but I could not open that confirmation
- Any ARIA-funded EEG or brain dataset
- Outside access to the Scaling Inference Lab
- The eight Safeguarded AI cybersecurity project awardees and their releases
- Whether the user's 'Inkling 2 mainnrpo' refers to anything ARIA-related: not understood

## Tinker

### What is usable

- Inkling 2 Mini, open-weights model from Thinking Machines Lab (released 20 Nov 2026), MoE looped transformer, about 20GB footprint, agentic-coding oriented; runs on a 32GB Mac via Ollama. Sampling and fine-tuning on Tinker.
  - Access: Weights public on Hugging Face; hosted use needs a Tinker API key (credits). Also free chat in Tinker Playground.
  - Terms: Announcement says open weights but names no licence: licence not confirmed. Params discrepancy: announcement says 3.4B active, pricing page says 5.4B active.
  - Url: https://thinkingmachines.ai/news/inkling-2-mini/
  - Quote: "Inkling 2 Mini is available for inference and fine-tuning on Tinker."
- Inkling 2 Small (594B total / 17B active, image input, variable effort), released 5 Nov 2026. This is the model the name 'Inkling 2' most likely means; there is also Inkling (975B, Jul 2026) and Inkling-Small (276B). Made by Thinking Machines Lab.
  - Access: Tinker fine-tuning and sampling (key needed); weights on Hugging Face since 12 Nov update; Playground.
  - Terms: Announced as Apache 2.0.
  - Url: https://thinkingmachines.ai/news/inkling-2-small/
  - Quote: "Inkling 2 Small's weights are now available for download on HuggingFace."
- Tinker training and sampling API (28+ open-weight models: Inkling family, Qwen3.x, GPT-OSS-20B/120B, Nemotron, GLM, Kimi, DeepSeek). You write the training loop locally; Tinker runs the GPUs.
  - Access: Key needed, pay per token (credits). Small models e.g. Qwen3-8B, GPT-OSS-20B, Inkling 2 Mini are listed as training models; sampling listed per model.
  - Terms: Pay per token; Inkling 2 Mini train $0.75/M (64K) , sample $0.50/M; Inkling 2 Small train $1.50/M, sample $1.00/M. Storage $0.10/GB/month.
  - Url: https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/
  - Quote: "Inkling 2 Small and Inkling 2 Mini sample up to 1M tokens on both training options."
- Tinker Python SDK (open source) and docs: three clients, ServiceClient, TrainingClient, SamplingClient. Exact method names and install line not verified (README fetched was a stub).
  - Access: Public repo; running needs TINKER_API_KEY.
  - Terms: Apache-2.0
  - Url: https://tinker-docs.thinkingmachines.ai/
  - Quote: "Write training loops locally — Tinker handles the GPUs."
- OpenAI-compatible inference endpoint for base models and your own fine-tuned checkpoints, chat completions and completions. Works with the standard openai Python SDK, so it drops into an OpenRouter-style client by changing base_url, api_key, model.
  - Access: Tinker (testing) endpoint works with the Tinker key; production endpoint is waitlist.
  - Terms: Beta, 'designed for testing your models'; rate limits not documented; unknown fields silently ignored (put reasoning_effort at top level, not extra_body).
  - Url: https://tinker-docs.thinkingmachines.ai/inference/openai/overview/
  - Quote: "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
- tinker-cookbook (post-training recipes, 4,301 stars), tinker-project-ideas (201 stars), batch_invariant_ops (MIT, deterministic kernels), inkling-verify (Apache-2.0), tinker-challenge.
  - Access: Public GitHub.
  - Terms: cookbook Apache-2.0; batch_invariant_ops MIT
  - Url: https://github.com/thinking-machines-lab
  - Quote: "tinker-cookbook | "Post-training with Tinker" | Apache-2.0 | 4,301"
- Serverless inference (beta) for Inkling and Inkling-Small only.
  - Access: Waitlist, not open signup.
  - Terms: Inkling-Small $0.30 prefill / $1.20 sample per M; images only via Inkling models on inference APIs.
  - Url: https://tinker-docs.thinkingmachines.ai/tinker/models/models_and_pricing/
  - Quote: "Access is by waitlist, not open signup."

### Best integration

Add "Inkling 2 Mini (Tinker)" to the dashboard model picker as a third agent backend next to Claude CLI and OpenRouter. User sees: pick it, press run, and the agent's per-round design proposals (layers, width, quantisation) stream in labelled with model id thinkingmachines/Inkling-2-Mini (exact Tinker model id string not confirmed, read it from the Tinker model list) and a per-run token cost line from the pricing table. Code: the existing OpenRouter client (openai SDK) is instantiated with base_url=https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1, api_key=os.environ["TINKER_API_KEY"], model=<Tinker model id>, calling client.chat.completions.create(...); the proposer backend registry gets one new entry, nothing downstream changes (batch fine-tune, Yosys, equivalence all stay). Stretch if time: log (task prompt, winning design JSON, chip size) from earlier runs and use the Tinker SDK (TrainingClient, then SamplingClient, then the same OpenAI-compatible endpoint with the checkpoint path as model) to LoRA fine-tune Inkling 2 Mini into the design proposer, and show picker entry 'Inkling 2 Mini, fine-tuned on ChipIn runs' with chips-found-per-round against the base model. Do not use Tinker for the EEG net fine-tuning itself: Tinker serves large LLMs with LoRA, the thousands of small chip-candidate nets stay on the GPU batch. Needs a working TINKER_API_KEY by Saturday night; the notes do not show one.

### Fallback

Show the picker entry "Inkling 2 Mini (Tinker): available, not used in this run", greyed, with the endpoint config and the one-line change that enables it, and run the demo on Claude or OpenRouter. Optionally one honest smoke call shown in the log only if a key works. Mention Inkling 2 Mini open weights can run locally via Ollama on a 32GB Mac (stated on the announcement) as a no-credit route, only claim it if actually run.

### What would be a false claim

- Saying ChipIn 'runs on Tinker' or 'was fine-tuned with Tinker' when the key was never used in the shown run.
- Saying the event or Thinking Machines is a supporter or gave credits: the Luma page lists only Callosum, Inherent Labs, ARIA and Fractile, and the team notes say credits are not confirmed to be for Tinker.
- Calling 'Inkling 2' one model: Inkling 2 Mini (26B) and Inkling 2 Small (594B) differ, and original Inkling is another model.
- Claiming Tinker fine-tunes the small EEG/chip networks, or that Inkling designs chips better than Claude without a measured comparison.
- Claiming serverless inference or the production endpoint is available to the team: it is waitlist.
- Stating a licence for Inkling 2 Mini or its active parameter count without caveat (sources disagree: 3.4B vs 5.4B).

### Question to ask at the event

Does the event's AI-credit allocation include a Tinker API key and budget for Inkling 2 Mini and Small on the Tinker endpoint, and where do we claim it?

### Event offer

Luma page: supported by Callosum, Inherent Labs, ARIA, Fractile; offers GPU environments, AI credits, mentors. No mention of Tinker or Thinking Machines. Team notes: the Discord has nothing about Tinker or credits; credits not yet received; the notes say it is not confirmed that the event's credits are for Tinker, and no teammate mention of Inkling2 appears in the notes folder.

### Not confirmed

- That the team holds Tinker credits, their amount, or that the event granted them (notes: not received, not confirmed)
- Who suggested 'inkling2' (not in the notes folder; only the web identification of Inkling 2 Mini/Small by Thinking Machines Lab was verified)
- Exact Tinker model id string for Inkling 2 Mini/Small (only thinkingmachines/Inkling:peft:262144 is quoted)
- Licence of Inkling 2 Mini
- Rate limits and concurrency quotas
- Exact SDK method names and install command (README fetched was a stub)
- Whether Tinker credits can be used on the OpenAI-compatible endpoint vs only the SDK (testing endpoint uses the Tinker key per docs)
- Whether Inkling 2 Small is on serverless (Tinker site says yes, pricing page says Inkling and Inkling-Small only)

## Teams funded by ARIA

### Programmes

- Scaling Compute (Nature-Inspired Computation opportunity space; Programme Director Suraj Bramhavar): 12 R&D Creators plus the Scaling Inference Lab
- AI Scientist (AI in Science): 12 projects, 245 applicants, 6m GBP over 9 months
- Precision Neurotechnologies (Scalable Neural Interfaces opportunity space; 19 teams; GBP 69m): https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects
- Massively Scalable Neurotechnologies (same opportunity space; 10 teams; GBP 50m): https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Activation Partners (ARIA scheme for ventures): https://www.aria.org.uk/activation-partners. Checked via search only. No neurotech startups named as funded under it were found. Not confirmed.

### Is each event supporter itself ARIA-funded

Fractile: yes, confirmed on ARIA's Scaling Compute page (\"Walter Goodwin, Fractile\", project \"Better Analogue in Memory Matrix-Vector Multiplication\"), https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators. Callosum: named on ARIA's page as \"Technology partner: Callosum\" for Scaling Inference Lab Cluster 2, with \"ARIA funding system integration and testing\" for each cluster, https://aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/scaling-inference-lab/; a direct ARIA grant is reported by press (Fortune, DCVC) but not confirmed on ARIA's or Callosum's own page (callosum.com home page does not mention ARIA). Inherent Labs: not confirmed; no ARIA page read names it, and searches found only third-party descriptions (a London AI lab building AI for scientific discovery, per Radical VC and TechCrunch).

### Top connections, with suggested sentences

- Normal Computing UK: "Normal Computing, funded by ARIA to build physics-based chips for AI, says it uses its own AI to design its chips; ChipIn applies the same idea of AI-designed silicon to a tiny medical sensor chip." (Their own words support the AI-designs-chips part, not any need for ChipIn. Say nothing about a relationship.)
- Fractile: "Fractile, funded by ARIA to show that in-memory compute can run AI models far faster, attacks the cost of AI hardware in the data centre; ChipIn attacks it at the other end, by wiring a small model's weights into logic gates so there is no weight memory at all." (Contrast only; do not say they would use it.)
- Signaloid: "Signaloid, funded by ARIA to develop hardware for approximate matrix inversion and now previewing an ASIC for physical AI and robotics, shows there is demand for small purpose-built AI silicon at the edge; ChipIn automates that design for a clinician's chosen bar." (Fits only because its own announcement is titled as an ASIC for physical AI and robotics; the funded work itself is linear algebra, so keep it as context, not a need.)
- 1. Sonalis Imaging (Imperial): "Sonalis Imaging, funded by ARIA to build an acoustoelectric brain-sensing helmet tested on pre-operative epilepsy patients, is working on the same problem we are, reading brain signals for epilepsy." Says nothing about needing our chip; its own page confirming the award is not confirmed.
- 2. Motif Neurotech with Rice (Brain Mesh): "Motif Neurotech and Rice, funded by ARIA for the Brain Mesh, millimeter-sized implant nodes that stream neural data, show why neural sensing has to fit in a tiny power budget, which is the constraint we design chips for." Claims no relationship. Their need for a chip is not in ARIA's words.
- 3. Yunlong Zhao's team at Imperial (Endovascular Acoustic Interfaces): "Imperial's team, funded by ARIA for sensors that need no batteries or conventional electronics, tackles brain monitoring for conditions like epilepsy from the other end; we cut the cost by shrinking the chip." This is a different approach, so use it only as a contrast and not as a customer.

### Funded organisations

Group: compute

- Fractile (Walter Goodwin) (Scaling Compute): Builds AI inference chips and is an event supporter. It attacks the cost of AI compute in the data centre, while ChipIn makes tiny fixed-weight chips for sensors, so the two are complementary and share no product. Own-page confirmation on fractile.ai: not confirmed (only the ARIA page was read). https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Normal Computing UK (Patrick Coles) (Scaling Compute (Thermodynamic Matrix Inversion)): Builds chips and uses AI to design them, so it is the closest to 'AI that designs hardware'. ChipIn is a different target (small, fixed, verified logic for sensors), so it is a parallel, not a customer or supplier. Funded-project text is on https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators. https://aria.org.uk/insights/developing-a-world-first-thermodynamic-computing-chip
- Callosum (technology partner, Cluster 2 of the Scaling Inference Lab) (Scaling Compute: Scaling Inference Lab (delivered by CommonAI CIC)): Software and systems orchestration across chips, not a chip designer. The ARIA page names it as technology partner and says ARIA funds the cluster's integration and testing; it does not say Callosum itself is a grantee. A direct ARIA grant to Callosum appears only in third-party press (Fortune, DCVC), so treat that as not confirmed on ARIA's pages. https://aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/scaling-inference-lab/
- Signaloid (Phillip Stanley-Marbell) (Scaling Compute): Builds chips, with an ASIC aimed at physical AI and robotics, so the nearest in spirit to edge hardware; its work is accelerating matrix inversion, not generating a netlist per task. Closest 'would care about edge silicon' link, but no stated need for what ChipIn does. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Rain AI UK (Jack Kendall) (Scaling Compute): Builds analogue accelerator chips; attacks AI cost from another direction. No real connection to a sensor chip. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Rain AI UK (Benjamin Scellier) (Scaling Compute): Training algorithms for analogue hardware, done in simulation; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Alphawave Semi (Tony Chan Carusone) (Scaling Compute): Chip-to-chip links for data centres; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Imec (James Myers): Heterogeneous Scale-Out Platform Simulator (Scaling Compute): Design-tool style work (simulation of system cost), but for data-centre systems; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Imperial College London (Aaron Zhao), University of Edinburgh (Luo Mai), University of Cambridge (Robert Mullins): Breaking Down the Compute Graph (Scaling Compute): Simulation tooling for AI training systems; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- University of Oxford (Noa Zilberman): Scalable AI Systems (Scaling Compute): Interconnect; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Cornell University (Peter McMahon): Low-Precision Training (Scaling Compute): Low-precision networks share a spirit with tiny quantised models, but it targets training; weak link. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- King's College London (Bipin Rajendran): Neuromorphic Matrix Multiplication (Scaling Compute): Attacks AI cost from another direction (training); no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- KU Leuven (Marian Verhelst, Wim Dehaene) (Scaling Compute): Chips for optimisation, not inference; no real connection. https://www.aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/meet-the-creators
- Quettaflop AI (Cluster 1), Oriole Networks (Cluster 3), Lumai (Cluster 4) (Scaling Compute: Scaling Inference Lab (technology partners)): Data-centre inference hardware and networking; no real connection. Same funding caveat as Callosum: named as partners, ARIA funds integration and testing. https://aria.org.uk/opportunity-spaces/nature-computes-better/scaling-compute/scaling-inference-lab/
- Constructor Knowledge Labs (Andrey Ustyuzhanin): MIND-MATTER (AI Scientist): The only AI Scientist project aimed at computing hardware: an AI scientist studying physical hardware. Same shape as ChipIn (AI agents exploring hardware design), but it studies device physics, not circuit synthesis. Genuine but loose parallel. https://aria.org.uk/ai-in-science/ai-scientists
- Other AI Scientist projects (none build chips): AminoAnalytica (pathogen diagnostics), Briefly Bio (wet-lab plant transformation), Deep Origin (endometriosis drug discovery), Edison Scientific with UCL (lysosome failure), Find What Matters with b.next (cell-free energy), Otter Quarks (ThetaWorld, battery degradation), King's College London (microbial protein), University of Liverpool (mobile robotic scientist), University of Oxford (Cancer AI Scientist), Lila Sciences (AI NanoScientist), Cultivarium (Hermes, DNA delivery) (AI Scientist): No real connection beyond the shared idea of an AI scientist. The Oxford project's text mentions "sovereign AI supercomputing" in a closed loop, but it is about cancer vaccines. https://aria.org.uk/ai-in-science/ai-scientists

Group: neuro-health

- Sonalis Imaging Ltd + Imperial College London (lead Oscar Calderon Agudo) (Precision Neurotechnologies, Non-invasive Interfaces): Epilepsy patients plus a head-worn sensing helmet make it the closest in theme, but it is ultrasound-based, pre-clinical and not EEG. If it ever became a wearable, it would be a possible customer for a small chip. Sonalis's own page confirming the award: not confirmed (only a third-party article, ingenia.org.uk, was found). https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?cardId=a-high-precision-non-
- Motif Neurotech + Rice University (lead Jacob T. Robinson), Brain Mesh (Precision Neurotechnologies, Non-invasive Interfaces): Tiny implant nodes that stream neural data need low-power compute, so they attack the same power-and-size problem from the implant side. ARIA's text does not mention chips. A Rice news release (news.rice.edu, 2025) reportedly names power and data circuits and a UK chip startup, MintNeuro; I read that only as a search summary and did not verify the wording. Not confirmed. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?cardId=brain-mesh
- Nir Grossman, UK Dementia Research Institute at Imperial College London (Precision Neurotechnologies, Non-invasive Interfaces): Stimulation, not sensing; no real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects
- Aimun Jamjoom, Barking, Havering and Redbridge University Hospitals Trust (Forest 1) (Precision Neurotechnologies, Non-invasive Interfaces): No real connection (mood, ultrasound imaging). https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects
- Gabriele Lignani, University College London (Precision Neurotechnologies, Remote Interfaces): Epilepsy treatment by gene therapy, a different route to the same disease; it builds no sensor or chip. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=remote-interfaces
- Karl Brune, Navira Ltd (Precision Neurotechnologies, Remote Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=remote-interfaces
- James Choi, Imperial College London (Precision Neurotechnologies, Remote Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=remote-interfaces
- Hadi Heidari, University of Glasgow (NEUROBOT, listed as Closed) (Precision Neurotechnologies, Remote Interfaces): Closed-loop epilepsy implants are an adjacent use for tiny low-power compute, but the project is marked Closed and the page says nothing about chips. Do not use. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=remote-interfaces
- Mengxing Tang (Imperial College London) + Mikhail Shapiro (Caltech) (listed as Closed) (Precision Neurotechnologies, Remote Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=remote-interfaces
- Kacy Cullen, University of Pennsylvania (Precision Neurotechnologies, Biological Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=biological-interfaces
- Rylie Green, Imperial College London (RESCUE) (Precision Neurotechnologies, Biological Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=biological-interfaces
- Andrew Jackson, Newcastle University (Precision 4D Control of Cortical Circuit Function) (Precision Neurotechnologies, Biological Interfaces): Closed-loop ML on brain signals, a loose analogy only; no epilepsy or hardware claim. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=biological-interfaces
- George Malliaras, University of Cambridge (Rebuilding the Nigrostriatal Pathway) (Precision Neurotechnologies, Biological Interfaces): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=biological-interfaces
- Future Adoption workstream, six academic teams: Mahnaz Arvaneh (Sheffield), Dennis Chan (UCL), Ben Seymour (Oxford), Martyn Pickersgill (Edinburgh), Jamie Brannigan (Oxford), Melanie Fleming (Oxford) (Precision Neurotechnologies, Future Adoption): Social-science and clinician-engagement work. It could inform clinician-set bars, but no direct connection; I did not read the modal text for each. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/precision-neurotechnologies/funded-projects?tabId=future-adoption
- Yunlong Zhao, Imperial College London (Endovascular Acoustic Interfaces for Scalable Neural Biomarker Readout) (Massively Scalable Neurotechnologies): Brain monitoring for epilepsy, attacking the same cost and power from the opposite direction (no electronics at the sensor), so it is not a customer. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Soyon Hong, UK Dementia Research Institute at UCL (Massively Scalable Neurotechnologies): Epilepsy therapy, no device; no real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Nicolette Driscoll, NeuroBionics (Massively Scalable Neurotechnologies): Implant stimulation for Parkinson's; its hardware may need low-power electronics but the page does not say so. A stretch. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Pietro Valdastri, University of Leeds (VINES) (Massively Scalable Neurotechnologies): A tiny wireless-powered implant is a power-limited device, but the page does not mention chips or sensing. A stretch. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Ed Boyden, MIT (Ultrasound Contrast Agents for Recording of Neural Activity) (Massively Scalable Neurotechnologies): No real connection (ultrasound recording). https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Guangzhao Mao, University of Edinburgh (NEURAL-TRAK) (Massively Scalable Neurotechnologies): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Polina Anikeeva, MIT (Remote Magnetic Neuromodulation with Bio-Magnetic Nanotransducers) (Massively Scalable Neurotechnologies): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Yujia Zhang, EPFL (ImmunoKnight) (Massively Scalable Neurotechnologies): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Henry Lee and Nili Ostrov, Cultivarium UK (SCENT) (Massively Scalable Neurotechnologies): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects
- Alon Galor, DART Biosciences (Massively Scalable Neurotechnologies): No real connection. https://aria.org.uk/opportunity-spaces/scalable-neural-interfaces/massively-scalable-neurotechnologies/funded-projects

### Stretch, do not use

- Saying any ARIA creator would be a customer, user or beneficiary of ChipIn: none of the pages says they need fixed-weight or medical sensor chips.
- Saying Callosum is funded by ARIA for a given sum or as a grantee: ARIA's page only names it technology partner for Cluster 2 with ARIA funding integration and testing; the grant is in press only (not confirmed on ARIA's own page).
- Calling Fractile, Callosum or Inherent Labs partners, mentors or users of ChipIn because they support the event.
- Linking Alphawave Semi, Oxford interconnect, Oriole, Lumai or Quettaflop (networking, optical, GPU pipelines) to ChipIn; the cost they attack is data-centre scale, not sensors.
- Linking the Imec and Imperial/Edinburgh/Cambridge simulators: they model data-centre training systems, not a single netlist.
- Saying MIND-MATTER designs chips: it studies charge transport in RNPUs, not circuit design.
- Linking any other AI Scientist project (bio, materials for displays, batteries): they are wet-lab or physical sciences with no hardware design.
- Saying ARIA has an AI-for-hardware-design programme: not found on the pages read. Do not claim it.
- Using the 1000x cost goal as a ChipIn claim: it is the Scaling Compute target for training hardware cost, not an edge-inference target.
- Do not say any funded team needs, uses or would buy ChipIn. No page says so.
- NeuroBionics, Leeds VINES and Glasgow NEUROBOT: implant or stimulation work with no sensing-chip need stated, and NEUROBOT is listed as Closed.
- Sonalis is ultrasound-based and pre-clinical, not an EEG headband, so avoid saying it is a customer or competitor.
- Motif and MintNeuro chip links come from a Rice release seen only as a search summary. Do not state them without opening that page.
- Gene, cell and drug delivery teams (Lignani, Hong, Navira, Cultivarium, DART, ImmunoKnight, Mao, Choi, Anikeeva), Future Adoption teams and organoid teams: epilepsy appears in some but they have no sensor or chip link.
- Do not claim ARIA funds ChipIn-type work, EEG headbands or seizure wearables; none of the 29 funded teams was found to build an EEG wearable or a low-power chip as the funded work.

### Not confirmed (ARIA research)

- Inherent Labs being funded by ARIA: not confirmed on any ARIA page.
- Callosum receiving a direct ARIA grant and its amount: not confirmed on ARIA's or Callosum's own page (press quotes of 2.9m USD differ).
- Fractile's own page confirming the ARIA award: not confirmed (only ARIA's page read; a 5m GBP figure appears only in third-party press).
- Individual award amounts for every creator: not confirmed.
- Which Scaling Compute creators use AI to design hardware beyond Normal Computing: not confirmed on the pages read.
- Whether Constructor Knowledge Labs is a company or academic team: not confirmed on the page.
- That ARIA has a separate programme or opportunity space for AI-designed chips or EDA: not found on the pages read.
- Callosum's specific wording on the Scaling Inference Lab from its own site: not confirmed (only press coverage).
- Funded organisations' own pages confirming each award: not confirmed for Sonalis, Navira, NeuroBionics, DART Biosciences and Cultivarium. Only Motif/Rice was seen, as a search-result summary, not opened. Third-party articles were not used as the basis for claims.
- Any chip or integrated-circuit work inside funded projects: not confirmed on ARIA's pages for any team. The MintNeuro and Rice power-and-data-circuit statement is unverified.
- Maker of Forest 1 (Jamjoom project): not confirmed.
- Whether DART Biosciences is a company: not confirmed.
- Neither funded-projects page showed an EEG wearable, wearable seizure sensor or low-power chip as funded work.
- Activation Partners: no funded neurotech startups found. Cohort 2 status after August 2026 is not confirmed.
- Counts: the ARIA page says 19 and 10 teams, matching the listings. The Future Adoption modals were not opened. Names, titles and tab descriptions are from the cards only.
- Other ARIA programmes outside the Scalable Neural Interfaces space, for example any on wearable or implantable sensing: not checked, so none are ruled in or out.
