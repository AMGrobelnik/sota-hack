# Master prompt: rebuild the ChipIn dashboard

Paste this whole file into the Claude session that owns the dashboard code (Adrian's).
Written against the live build at chipin.space/dashboard (round 5,
`dashboard/variants/h1.html` on `amg/frontend`). Code freeze is 14:45 on Sunday 22 Nov;
demos start at 15:00. Do not break the live site: work on a copy or a new variant and
switch over only when it runs.

---

## 0. How to work

1. **First walk the product end to end and report (section 1). Do not change code yet.**
2. Then propose a layout and a delete list (sections 3 to 6). Push back on anything
   wrong or unbuildable in the time.
3. Only after agreement, build. Smallest working version first, then the extras.
4. If what you see in the running product contradicts this document, trust the running
   product and say so.

## 1. FIRST: walk the whole workflow before changing anything

The brief below was written from the page source and the intake screen only. Go through
the product end to end as a medical device manufacturer would, and report back:

1. Enter a real brief at the intake screen, for example "a single-lead ECG adhesive
   patch that detects atrial fibrillation, 90% sensitivity and 85% specificity", and go
   through every question it asks (the recordings question, the public-data question,
   the assumptions).
2. Watch the full run play. Note what the screen shows at each stage, what is legible and
   what is noise, and how long it holds attention with nothing to do.
3. On the result, open every view: Overview, Chat, Visual, and each of the six Visual
   tabs (Device, Chip, Fine-tuning, Signal, Patients, Why this chip wins). Open Configure
   and all five of its tabs.
4. For each panel, answer one question: **does this help the user decide how big their
   chip should be?** If not, it is a candidate for deletion.
5. Report what exists, what is duplicated, what is decoration, and where the trade-off
   between accuracy and chip size is actually visible (reading of the source: nowhere).

## 2. What Oran asked for, in his own words (his framing wins where it differs)

- The dashboard has too much on it and is hard to interpret. It has to be really simple
  and easy to use; device makers judge a tool first on whether it is easy to use.
- The device render and the sensor diagram are not wanted. "If I'm a medical device
  manufacturer, I don't need to see the device and how it would look, and where it says
  chip and then sensors on the patch."
- **The chart is the main thing on the overview:** how small the chip is and how
  accurate it is, together. Then the chip, and a breakdown of how it got there.
- The user types a brief such as "build a patch for detecting AF, single-lead ECG, 90%
  sensitivity, 85% specificity". Their accuracy requirement is the input. The platform
  answers: given that bar, what is the smallest chip we can design, and what does that
  bring them?
- It asks whether the user has their own dataset, or should use public datasets.
- There should be an honest **confidence** indication: with little data it must not
  claim to be confident.
- Keep the funnel from thousands of designs down to one chip.
- "What it means for one newborn" restates sensitivity and specificity. Simplify it.
- **Cost:** going up in accuracy, how much more in gates and money; keeping the chip
  small, how much is saved, including battery life.
- **The battery and regulatory cliff, the thing he wants most:** the point where higher
  accuracy pushes the battery from a coin cell to a rechargeable one or bigger, what that
  means for regulation, and the point where the device stops being disposable. (Read
  the caution in section 7 before building it.)
- Show the other things a device maker might come for, not only the happy path.
- Above all: show the workflow for how it arrived at the chip, and the trade-offs the
  company is making.

## 3. The user and the question

The user is an engineer or product lead at a **medical device company**. Not a
clinician, not a patient. They have a device concept and a clinical bar, and one
question:

> **"What is the smallest, cheapest chip that still clears my clinical bar, and what do
> I give up by shrinking it further?"**

If a panel does not help them decide how big their chip should be, cut it.

## 4. The main problem: the chart plots process, not trade-off

`roundChart` puts **round number on the x-axis**: accuracy as a line across rounds,
chip size as a separate bar chart underneath. The two quantities the user trades are on
two charts, indexed by something they do not care about.

**Fix: one scatter chart. Gates on X, the clinical metric on Y.**

- One dot per evaluated design, not one per round. Keep per-candidate results (`vs`
  carries `{r, worst, gates}`) so the cloud of dots is real.
- Pareto frontier through the best designs.
- Designs that fail the bar: greyed, not hidden.
- The user's clinical bar as a horizontal line (keep the existing dashed 90% treatment).
- Label the axis honestly: **worst-case unseen patient**, not the mean.
- The thousands-to-one funnel (Oran wants it) and any round-by-round progress go in a
  small strip above or below the chart. Process, not product.

## 5. Delete, move, keep

**Delete from the overview**

- "The sensor" panel (`.sensp`, the `mount3D` / `buildDevice` render, "N of 19 electrode
  positions" / "N of 8 light paths"). Remove the Device entry from `VIS`.
- "What it means for one {patient}" (`#ptlh`, `#ptl`, `#miss`): move behind the Patients
  visual tab.
- The right rail (`#notif`, `#wlist`, `#srcs`): collapse to one "Where this comes from"
  affordance.

**Keep (they look cuttable and are not)**

1. **False alarms per hour.** Specificity in the unit that decides whether staff keep the
   device on. Alarm fatigue is why monitors get switched off. Headline tile.
2. **Warning lead time** ("flagged N seconds before it was obvious"). A device spec in its
   own right.
3. **"Judge by the worst."** The code evaluates on the hardest unseen patient, not the
   average. Strong and currently invisible: label it on the chart.
4. **The gate circuit animating on a live signal** (Chip visual): the clearest picture of
   "the model is the chip". Drill-down in the inspector, not the overview.

## 6. Answer in the units the user asked in

- Move **target sensitivity and specificity onto the main spec screen**, not the
  Configure tab. Entering them draws the lines on the chart.
- Headline the result as **sensitivity and specificity, pass or fail against the user's
  bar**, then the other tiles.

## 7. The consequence bands (Oran's priority), built honestly

Render shaded vertical bands behind the scatter marking where crossing a gate count
changes the device's power class, with each boundary labelled with what changes:

- **Primary coin cell**: single use, no charging circuit, no reprocessing between
  patients.
- **Rechargeable lithium**: charging circuit and contacts, thermal limits for parts on the
  skin, cleaning and reprocessing validation if reused, service life and cycle
  degradation, a reusable product.
- Mark the disposable/reusable commercial boundary on the same axis.

The sentence the product should produce: "92% sits inside the coin-cell band. 95% pushes
you into rechargeable: a reusable device with reprocessing validation and more
regulatory work. Is three points worth that?"

**Cautions before building (do not skip):**

1. **Do not build the cost story on die area.** At about 2,000 to 10,000 gates the chip is
   pad-limited: die size is set by the I/O pads, so silicon area and unit cost barely move
   across the range. The gradient that matters is gates, then power, then battery class,
   then device class, then regulatory burden.
2. **Chip power may not be what moves the battery class.** A few thousand gates of fixed
   logic draws very little; the sensor front end, the radio and any camera usually
   dominate a device's power budget. Compute the bands on **total device power**, with
   the chip as one line in it, and show the chip's share. If the chip is a small share,
   say so: "the chip is never your battery bottleneck" is itself a selling point. Do not
   imply the classifier's gate count alone moves a device from coin cell to rechargeable
   unless the power numbers show it.
3. **Lithium coin cells are lithium batteries too.** Do not claim coin cells avoid lithium
   transport testing (UN 38.3); the difference between the bands is charging, reuse and
   reprocessing, not whether lithium rules apply.
4. **The thresholds are unsourced.** Hardcode them and label them visibly as illustrative
   until there are real power-per-gate and device-power figures. Say "more regulatory
   work", not "a different regulatory pathway", unless that is checked.

## 8. Honesty: one plain headline, three visible parts

Oran wants a confidence indication; a single blended score cannot be defended. So show a
plain headline ("How sure is this? Low: 96 positive cases in the test set") built from
three separate, labelled indicators that are always visible beneath it:

1. **Clinical confidence interval.** A Wilson interval on sensitivity and specificity from
   test-set size and positive-case count, as error bars on the dots. When it is wide, say
   plainly that 92% and 95% cannot be told apart with this much data.
2. **Generalisation risk.** Qualitative: single database, one population, no external
   validation, how the split was made.
3. **Engineering estimate confidence.** Power, area, node, cost.

## 9. Separate measured from estimated (non-negotiable)

Gate count and logic depth come from synthesis and are measured. Power, die area,
process node and unit cost are estimates. One visual convention throughout (for example
estimates in italics with a dotted underline and a tooltip naming the assumption).

## 10. Cost assumptions panel: editable, on screen

Expose the cost model's inputs (annual volume, process node, wafer cost, battery
chemistry and capacity, assembly cost) as editable fields with outputs recomputing live.
Device companies have their own quotes and trust an editable model over a black box.
Show both directions Oran asked for: what going up in accuracy costs, and what staying
small saves (including battery life).

## 11. Target overview layout

1. **Header:** the run, the device, the clinical bar with pass or fail.
2. **Result tiles:** sensitivity and specificity (each against the bar), false alarms per
   hour, lead time, gate count, the confidence headline.
3. **The frontier chart, dominant:** scatter, Pareto, clinical bar lines, consequence
   bands, confidence-interval error bars, "judged on the worst unseen patient". Funnel
   strip alongside.
4. **Inspector (right, for the selected dot):** measured against estimated table, the
   chip animating on a signal, exports (Verilog netlist, verification report).
5. **Everything else behind tabs.**

## 12. Demo content: which numbers are real

The only measured results so far are the AF-from-single-lead-ECG feasibility run;
everything in the seizure and brain-oxygen demo runs is simulated. "Simulated run, demo
data" covers it, but judges will ask "which numbers are real?" and we need a crisp
answer.

Oran's decisions: the demo case studies are **Incubator Watch** (neonatal radar plus
thermal infrared: apnoea, bradycardia, temperature warnings) and the **neonatal EEG brain
monitor** (seizures and brain-injury grade, real open data: Helsinki and Cork, CC BY 4.0).
AF is not a demo case. Spec and data: `context/oran-notes/2026-11-21-build-brief.md` on
`oran/context`.

So, in order of preference:

1. **Run the neonatal EEG case on real data before the freeze** so the screen carries
   measured figures for a case we actually present.
2. If that is not possible, keep the demo runs clearly labelled simulated, and add a
   **"Measured so far"** drawer with the AF feasibility figures as proof the pipeline
   runs:
   - 2,330 gates after synthesis, longest path 52 cells.
   - Circuit: sensitivity 0.7315 and specificity 0.8790 (window level); 0.8333 and 0.8764
     (record level).
   - Full-precision baseline: 0.9745 and 0.9334 (window); 0.9688 and 0.9531 (record).
   - Verification: 3,880 of 3,880 test windows identical, 0 mismatches.
   - Search: about 1,625 candidates per minute batched (K=256) against about 27.6 one at
     a time, about 59 times.
   - Data: PhysioNet/CinC 2017, 5,788 recordings, split by recording; 800 test recordings,
     96 with AF.
   - The circuit is clearly less accurate than the full-precision model: a model gap, not
     a hardware gap. Do not hide it.

Also check the demo runs match the locked cases (the current runs are seizure detection
and brain oxygen; Incubator Watch is radar plus thermal, not brain oxygen). Flag the
mismatch rather than silently changing the science.

## 13. Sponsors, lightly

Keep it small; simplicity comes first. Use "built at" and "supported by", never
"partnered with"; text names, no logos; no Hugging Face.

- Footer credit: "Built at the SoTA Scientific Parallelism Hackathon, London, November
  2026. Supported by Callosum, Inherent Labs, ARIA and Fractile."
- If the funnel strip labels stages by hardware (agent, GPU batch, gate synthesis,
  check), that is the Callosum point. A "weight memory traffic: 0 bytes" line in the
  inspector is the Fractile point. The clinician setting the bar on the spec screen is
  the Inherent point. Details: `context/oran-notes/2026-11-21-sponsor-placements.md`.

## 14. Secondary flows, only if time allows

1. **Feasibility gate:** "no design in this family clears 90/85 on this data" is a
   valuable result. Design for the negative.
2. **Compare two designs side by side:** how hardware and clinical teams settle it.
3. **Subgroup sensitivity as a search constraint**, not just a reported number.
4. **Benchmark against a published claim or a frontier model** on the same data.

## 15. Principles

- The frontier chart is the product. Everything else is a drawer off it.
- Clinical bar in, silicon out. Answer in the units of the question.
- Never show a number without showing whether it was measured or estimated.
- If a panel does not help decide how big the chip should be, cut it.
- Simple enough that a device engineer understands the result in ten seconds.
