# SoTA Scientific Parallelism Hackathon, London, 21 to 22 Nov 2026

Everything gathered for this one hackathon: event facts, judging,
team, constraints, sponsors, every idea considered, the dialysis-graft
brief and its fact-check, past events, both sets of Granola meeting
notes, and the raw research results.

Status early afternoon, Sat 21 Nov 2026: the team is at the event;
no project chosen yet; compute credits not yet received. All idea
panels have finished, including the one aimed at technical judges.

## Event

- **Name**: Scientific Parallelism hackathon. The central question:
  which scientific questions could we investigate better if
  computation were faster or ran at greater scale?
- **Organiser**: Society for Technological Advancement (SoTA), hosts
  Jamie and Matvey.
- **Supporters**: Callosum, Inherent Labs, ARIA (the UK's Advanced
  Research and Invention Agency) and Fractile.
- **Page**: <https://luma.com/scientific-parallelism>
- **When**: Saturday 21 Nov 11:00 to Sunday 22 Nov 18:00.
- **Where**: Halkin, 1-2 Paris Garden, London SE1 8ND. An earlier
  King's Cross venue is out of date.
- **Ticket**: Adrian holds an approved Hacker ticket.
- **Prizes**: first £5,000 plus a demo slot at ARIA's AI for Science
  Summit (26 Nov, Manchester); second £2,500; third £1,000.
- **Compute**: GPU environments and AI credits. Credits come through
  a link from the organisers. The Luma page names no GPU model. Event
  Discord (21 Nov 2026): nothing about Tinker or credits is posted
  there, and the organisers had not answered the GPU question by 13:49
  on Saturday; ask them in person.
- **Tinker**: Thinking Machines Lab's API for fine-tuning and sampling
  open-weight models with LoRA adapters. That the event's credits are
  for this service is not confirmed.
- **Sunday timetable** (event Discord, 21 Nov 2026): final hacking and
  demo prep 13:00 to 14:45; judges' briefing 14:45 to 15:00; demos and
  judging 15:00 to 16:30; deliberation 16:30 to 16:50; winners 16:50 to
  17:00.
- **Rules** (event Discord, 21 Nov 2026): at most 4 per team is
  recommended. Pre-written code is fine if the team says clearly what
  was done on the day. Own hardware is allowed.
- **Challenges** (event Discord, 21 Nov 2026): three example challenges
  were shown in the opening talk, at least one on astronomy. None is
  posted on Discord. Whether teams may still bring their own idea was
  asked there and not answered.
- **Possible overlap** (event Discord, 21 Nov 2026): one participant
  lists massively parallel scientific falsification and autonomous
  research swarms as interests.
- **Discord check**: runs about every 10 minutes until the event ends
  (Sun 22 Nov 18:00). Digest:
  [notes/2026-11-21-discord-digest.md](notes/2026-11-21-discord-digest.md).

## Judging

Judging is at **15:00 on Sunday 22 Nov**.

The organisers' slide, "What judges are looking for", is the
authority on the criteria
([photo](judging-criteria-slide.jpeg)). Its wording:

1. Correctness & assumptions: preserve intended behaviour; explain
   and justify simplifying assumptions.
2. Fundamental reshaping: rethink the problem to expose
   opportunities for parallelism.
3. Meaningful speedup: compare performance with a credible, relevant
   baseline.
4. Scientific value: show useful results, sound methods and
   convincing technical evidence.

Footer: informative negative results count too; a well-explained
failure to achieve a speedup can still win a prize.

The opening-talk notes list the second criterion as "novelty". The
slide says "fundamental reshaping", and the slide wins.

- 21 Nov 2026: Adrian expects the judges will probably be the same as at
  SoTA's "Trust Everything" hackathon with ARIA in March 2026: Alex Obadia
  (ARIA programme director), Nicola Greco, Awais Rashid and Jamie. This is
  his expectation only. No judges are published for this event. The check
  found no evidence that the March judges return: Alex Obadia and Awais
  Rashid are tied to ARIA's Scaling Trust programme, not its compute
  programme, and public pages do not confirm who judged in March. See the
  [judges check](notes/2026-11-21-judges-check.md).

Team background section left out of the shared copy.

## What Adrian said (20 to 21 Nov)

Paraphrased from his messages in the planning session. His latest
word wins.

### Final constraints (as of 21 Nov)

- Hardware means compute hardware of the kind the sponsors build,
  not any hardware.
- Build an AI-scientist type system that works digitally and
  advances scientific discovery in general, rather than solving one
  problem.
- Make it visual.
- Biology is optional: do not over-focus on it, but include some biology or medical element so the team's biology-side member can use their skills (21 Nov 2026).
- The judges are technical and know little biology.
- Doctors' backing is available for any idea, so it is not a deciding
  factor.

### How the constraints changed

The first version (20 Nov, afternoon) had four constraints:
hardware, AI for science, biotech, and something visual. It is
superseded. The changes, in order:

1. 20 Nov, early evening: doctors can back any idea, so stop weighing
   it.
2. 20 Nov, evening: the system must work digitally, AI-scientist
   style, advancing discovery in general, not one specific problem.
3. 20 Nov, evening: hardware means compute hardware like the
   sponsors build, not just any hardware.
4. 21 Nov, early afternoon at the event: the judges are more
   technical and know little biology, so ideas need not be very
   biological; a bit of a biology spin helps but is optional.

### Team and status

- Team of three: Adrian (AI systems for scientific discovery),
  Antonio and Oran. One of them is a medical student, and the team
  has a biotech person.
- Early afternoon, Sat 21 Nov: at the event; project not decided;
  compute credits not yet received (expected soon). He asked whether
  the Tinker credits had arrived, and asked for the event's Discord
  to be checked about every 10 minutes for event news and anything
  relevant to the ideas.
- Judging is at 15:00 on Sunday 22 Nov.
- He asked who the judges are (not published), how often this
  hackathon has run (first on this theme; SoTA has run at least nine
  hackathons on other themes, see [past-events.md](past-events.md)),
  and the first prize (£5,000 plus the ARIA demo slot).

### Directions he raised and what was found

- **Biotech-specific chips**: very few exist (Anton and MDGRAPE for
  molecular dynamics, Illumina's DRAGEN for genomics); the event gives
  GPUs, not chip design tools, so the fit is optimising a biology
  workload on GPUs.
- **Biochips**: four kinds (lab-on-a-chip, organ-on-a-chip, sensing
  chips, living neurons on electrodes); became the biochip panel in
  [ideas.md](ideas.md).
- **The Leeds virtual heart-valve startup**: adsilico, a Leeds
  spinout that raised £10m (Oct 2026) for in-silico device trials on
  virtual patients. Pure simulation, not organ-on-a-chip.
- **Cells as computers (the Swiss company)**: FinalSpark runs brain
  organoids as remote processors. Simulating genetic circuits is
  useful for design; simulating neuron chips is weak, since no
  validated model of organoid learning exists. A GPU never makes the
  biological computation itself faster.
- **Embryo selection**: Nucleus Genomics (Nucleus Embryo) uses
  polygenic scores; a parallel angle is simulating how much selection
  really gains. Divisive for judges; the team call dropped it over
  data.
- **An agent simulating a single cell**: the agent should run a
  simulator, not play the cell. Whole-cell models cannot be built in
  a weekend; metabolism-only models are easy to run.
- **Dialysis graft**: he pasted the project brief and another
  assistant's answer on data; both are summarised in
  [dialysis-graft.md](dialysis-graft.md). Its first gap was the lack
  of an AI-for-science loop; agent versions were sketched.
- He also asked for an investor's view of the first five ideas; it
  was given in the session and not kept as a file.

## Current shortlist

No pick yet. Claude's recommendation, after re-scoring against the
judging slide (see [ideas.md](ideas.md)):

- **The parallel AI scientist** (technical-judges panel, rank 1,
  31/35): the OpenEvolve circle-packing loop on local models, run
  with 16 or 64 proposals in parallel against the sequential loop;
  also measures how discovery speed depends on token rate.
  Fallback: ECG leads (Lead Lattice) if model serving is not working
  within two hours of getting GPUs.

Other candidates, one line each:

- **Light Switch** (panel 1, rank 1, 30/35): agent-designed micro-LED
  light patterns that stop spiral-wave arrhythmias in thousands of
  simulated heart-on-chip tissues at once.
- **Bits per Verdict** (compute panel, rank 1, 29/35): the same heart
  workload, but the AI scientist finds the fewest bits of precision
  its own conclusions need; speaks to Fractile and ARIA.
- **Lead Lattice** (panel 2, rank 1, 30/35): an AI scientist that
  trains one small model per ECG lead subset (all 4,095) packed on
  one GPU. Strong on all four slide criteria in Claude's re-scoring;
  the technical-judges panel dropped it as too biological.
- **DEP-Agent** (biochip panel, rank 1, 30/35): agent-written
  electrode patterns for a chip that sorts tumour cells from blood,
  checked against the commercial ApoStream device.
- **Dialysis graft sweep** (the original brief): GPU lattice
  Boltzmann search over thousands of dialysis-graft join shapes;
  fact-checked, with a corrected claim set.

## Resources

- Idealab.AI database (<https://idealab.ai/#database>), pointed to by Adrian
  on 21 Nov 2026 as a place to look for ideas and for prior work. First look:
  about 1.4 million generated startup ideas (Idealab.AI, Bill Gross), with no
  code, data or results visible. The search ran on 21 Nov 2026 (12 queries,
  10 full briefs and 4 intro-only, no account needed). Matches were weak and
  none is close to a shortlist idea. The useful parts are pitch material ("why
  now" lines, competitor names generated by the site and not verified) and a
  pointer to IBM's AIHWKIT toolkit. Notes:
  [2026-11-21 idealab search](notes/2026-11-21-idealab-search.md).

## Files

- [sponsors.md](sponsors.md): what each supporter builds and wants.
- [ideas.md](ideas.md): every idea, by panel, with scores and kills.
- [dialysis-graft.md](dialysis-graft.md): brief, fact-check, prior
  work, compute sizing.
- [past-events.md](past-events.md): past SoTA winners, ARIA summits.
- [notes/2026-11-20-team-call.md](notes/2026-11-20-team-call.md):
  team call notes (Antonio).
- [notes/2026-11-21-opening-talk.md](notes/2026-11-21-opening-talk.md):
  opening talk notes (Oran).
- [notes/2026-11-21-discord-digest.md](notes/2026-11-21-discord-digest.md):
  event Discord digest, read Sat 21 Nov 2026.
- [notes/2026-11-21-judges-check.md](notes/2026-11-21-judges-check.md):
  check of who judges, from public pages.
- [judging-criteria-slide.jpeg](judging-criteria-slide.jpeg): photo
  of the judging slide.
- [data/](data/): raw research results as JSON.

The JSON files in `data/` keep the full findings, with every source
URL, so they survive after the temporary copies are cleared:

- `past-events.json`: past SoTA winners and ARIA summits.
- `idea-panel-1.json`: first idea panel.
- `idea-panel-biochip.json`: biochip idea panel.
- `sponsors-and-compute-ideas.json`: sponsor profiles and the
  compute-hardware idea panel.
- `idea-panel-2.json`: second idea round.
- `dialysis-graft-verification.json`: fact-check of the graft brief.
- `idea-panel-technical-judges.json`: idea round for technical
  judges, biology optional.
