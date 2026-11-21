# Sponsor placements for the site and dashboard (for Antonio / Adrian), 21 Nov 2026

Where to name the sponsors on Chipmonk (chipin.space) and in the dashboard. The site
currently names none of them.

Source: the Luma event page, "SoTA Scientific Parallelism Hackathon, supported by
Callosum, Inherent Labs, ARIA and Fractile". Hugging Face is no longer involved (the GPU
credits were withdrawn on 21 Nov), so do not mention it.

## Rules

- Say "built at" and "supported by". Never "partnered with" or "powered by": we have no
  partnership, and implying one backfires with these exact judges.
- Text names, not logos, unless the organisers confirm logos are fine.
- Each sponsor line states their thesis in our product's terms; it does not claim they
  use or endorse Chipmonk.
- Do not mention the ARIA summit slot on the site: that is the prize, not something we
  have.

## Landing page

### 1. Badge under the hero, repeated in the footer

```html
<p class="event-credit">
  Built at the SoTA Scientific Parallelism Hackathon, London, November 2026.
  Supported by Callosum, Inherent Labs, ARIA and Fractile.
</p>
```

### 2. "Why this works" strip (three cards)

```html
<section class="why-strip">
  <article>
    <h3>No memory to fetch</h3>
    <p>Memory bandwidth, not arithmetic, is the bottleneck in AI hardware, the thesis
    behind Fractile. We take it to the extreme: the weights are wired into the gates, so
    the model fetches nothing from memory.</p>
  </article>
  <article>
    <h3>Every stage on the hardware it suits</h3>
    <p>Agents reason, GPUs train thousands of designs at once, synthesis turns the
    winner into gates. Different stages, different chips, the heterogeneous-compute
    idea Callosum works on.</p>
  </article>
  <article>
    <h3>AI scientists, clinician in charge</h3>
    <p>AI scientists propose, train and verify; a clinician sets the bar the chip must
    clear. Humans and AI working together, as Inherent Labs argues science should.</p>
  </article>
</section>
```

ARIA: only add a line once its wording is checked against ARIA's own pages (for example
its compute programme). Until then ARIA appears in the event credit only.

## Dashboard

1. **Pipeline bar labelled by hardware**: `Agent (LLM) -> GPU batch -> Gate synthesis ->
   Bit-exact check`, each stage showing where it runs (Callosum).
2. **Memory panel on the results**: `Weight memory traffic: 0 bytes (weights wired into
   gates)`, next to gate count and depth (Fractile).
3. **Human approval step**: before the search runs, the clinician sets or approves the
   clinical line (events caught, false alarms per hour); show who approved it (Inherent).
4. **Footer credit**: the same event-credit line as the landing page.

## Pitch

Name each sponsor at the moment the demo shows their idea (pipeline bar: Callosum;
memory panel: Fractile; approval step and benchmark against frontier models: Inherent;
real clinical problem and open data: ARIA). Remove the Hugging Face judge line from the
pitch notes.
