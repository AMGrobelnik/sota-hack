# Sponsor wording check, 2026-11-21

The three proposed lines (Fractile, Callosum, Inherent Labs) each overstate what the supporter says on its own pages; corrected wording is below.
Use names as plain text only, no logos: Fractile's terms and ARIA's terms require permission.

## Fractile

**Who:** UK inference-chip company (fractile.com) founded in 2022 by CEO Walter Goodwin; it builds chips and systems for fast, long-context inference of frontier AI models. The Luma page says only "supported by", never "sponsor" or "partner".

**Their thesis:**

- "The technical and economic limits on inference speed, above all from memory bandwidth that has failed to scale on current architectures, are what is constraining progress." (https://fractile.com/manifesto)
- "We bet everything on the logical conclusion: that the only way to truly unlock this latent value, to make speed viable at scale, was to radically re-invent the hardware that we run our frontier AI models on." (https://fractile.com/manifesto)
- "To compress that month into a day, we will need to generate output at ~1,200 tokens per second, while handling the complexity and capacity challenges of operating large models at very long contexts." (https://fractile.com/manifesto)

**Unsupported in the proposed line:** "Memory bandwidth, not arithmetic" (the contrast with arithmetic is not on their pages); "the bottleneck in AI hardware" (they say a limit on inference speed, not on all AI hardware); "the thesis behind Fractile" (their thesis is broader: speed from query to output, so re-invent the hardware); "We take it to the extreme" (implies Fractile does the same thing). Nothing on their pages says they wire weights into gates or remove memory; their jobs page lists a "Foundry Engineer - DRAM" role.

**Corrected line:** Built at an event supported by Fractile, whose founder writes that inference speed is limited "above all from memory bandwidth that has failed to scale on current architectures". ChipIn goes after the same cost from a different direction: the chosen model is compiled to gates with its weights wired in, so it has no weight memory to fetch from.

**Do not claim:**

- That Fractile uses, endorses, partners with or favours the weights-in-gates approach.
- That their chip is hardwired or has no memory.
- Kinship with their LLM and frontier-model focus (about 1,200 tokens per second at very long context); ChipIn is a tiny fixed model for an EEG sensor.
- "In-memory compute" as their thesis; only third-party reports use that phrase.
- Their funding or speed figures (for example $220M, 25x) as your own.
- Any Anthropic or customer link; the only source is secondhand.

**Hard question they may ask:** Your weights are frozen into gates, so each new model needs a new chip. Does that design hold for anything beyond one tiny fixed model such as a seizure detector? What about models that must be updated, or the large long-context models Fractile targets, where the weights cannot be hardwired and memory bandwidth still limits speed? Likely follow-up: what does the verified netlist cost in area and power against a small model on a standard microcontroller?

**Name and logo rule:** Terms of Use (https://fractile.com/assets/legal/terms-of-use.pdf, linked from https://fractile.com/legal): "Our name and our logo are trade marks owned by us. You are not permitted to use any of our trade marks without our prior written approval." Write the name as plain text in a factual statement ("supported by Fractile"); no logo without written approval from hello@fractile.ai.

**Not found:**

- A Fractile statement contrasting memory bandwidth with arithmetic, or calling memory bandwidth the bottleneck of AI hardware in general.
- The phrase "in-memory compute" on any Fractile-owned page.
- Any technical blog, paper or architecture page on their chip design (the site has only the manifesto, How we think, Jobs and Legal).
- Any Fractile statement about hardwired weights, weights-in-gates or removing weight memory.
- A brand or press kit or logo guidelines beyond the trade-mark line in the Terms of Use.
- The exact wording of Fractile's role at the event.

## Callosum

**Who:** Callosum (callosum.com), London; "the Intelligent Systems Company", selling Tailored Inference APIs that match workloads to models and chips.

**Their thesis:**

- "The problems worth solving are inherently heterogeneous, and so the intelligence we build to solve them must be too." (https://callosum.com)
- "The next substantial leaps in AI capability, cost and speed will come from this heterogeneity." (https://callosum.com/blog/welcome-heterogeneous-intelligence)
- "We disaggregate these systems, splitting workflows across models and hardware" (https://callosum.com/product)

**Unsupported in the proposed line:** The gist (different stages on different chips) is close, but: "train" (their product page is about inference and says nothing on training); "turns the winner into gates" (nothing on chip design or synthesis); "different chips" if it implies ChipIn does heterogeneous runtime routing (ChipIn runs stages on GPUs, then a software synthesis step, with one chip as output). "The idea Callosum works on" can read as an endorsement; keep to their stated view.

**Corrected line:** Built at the SoTA Scientific Parallelism Hackathon, supported by Callosum, whose thesis is that the next leaps in AI come from heterogeneity, with the right model on the right chip; ChipIn pushes that to its end, an AI-designed chip made to fit one model.

Backing quote: "The next substantial leaps in AI capability, cost and speed will come from this heterogeneity." (https://callosum.com/blog/welcome-heterogeneous-intelligence). Also: "entirely new accelerator designs running new model architectures" (https://callosum.com/blog/the-principle-of-maximum-heterogeneity).

**Do not claim:**

- That Callosum uses, endorses, partners with or favours ChipIn, or that ChipIn is built on Callosum.
- That Callosum designs chips; their product page does not say so, and they partner with silicon companies.
- That Callosum does training or fine-tuning orchestration; the product page is inference-only.
- Their "co-evolve chips and intelligence" phrase as if ChipIn does what they do; ChipIn bakes one model into one chip, the opposite of routing across many accelerators.
- "Multi-Agent Scientific Discovery" as their thesis; it appears only as a chart label.

**Hard question they may ask:** Your final chip is a single fixed model hard-wired into gates, with no weight memory. How is that heterogeneous compute rather than a single-purpose ASIC, and what happens when the model needs updating, or when a general accelerator would serve the same clinician bar at lower total cost, including the cost of the thousands of GPU fine-tunes and the synthesis flow?

**Name and logo rule:** Not found. callosum.com lists no brand, logo or press usage page; https://callosum.com/terms returns 404; only the contact press@callosum.com is given. Name them in plain text as a supporter; no logo without asking press@callosum.com.

**Not found:**

- A public rule on using the Callosum name or logo.
- Any Callosum statement on training or fine-tuning workloads.
- Any Callosum statement on designing chips, hardware synthesis, or gate-level or no-weight-memory chips.
- Any Callosum page on the hackathon itself (only the Luma page was read).
- Full text of the blog posts "The Global Integrator of Heterogeneous Compute", "Making Heterogeneity Programmable" and "We Are Scaling Heterogeneous Compute" (titles only).
- Luma naming: the title reads "SoTA Scientific Parallelism Hackathon | With Callosum, Inherent, ARIA + Fractile" and the description "supported by Callosum, Inherent Labs, ARIA and Fractile" (from a tool summary of https://luma.com/scientific-parallelism, not verbatim page text).

## Inherent Labs

**Who:** Inherent Labs (inherentlabs.ai), a London AI lab and Public Benefit Corporation building a general-purpose "AI scientist" (Faraday, trained on its Replica paper-replication suite). Luma says "Inherent Labs" in the body and "Inherent" in the title.

**Their thesis:**

- "AI’s promise lies not in automating science, but in enabling a new kind of collective intelligence" (https://inherentlabs.ai/)
- "leverages the comparative advantages of humans and machines" (https://inherentlabs.ai/)
- "we are developing general-purpose inventive AI that accelerates research across domains" (https://inherentlabs.ai/)
- "while firmly keeping humans in the loop" (https://inherentlabs.ai/research/training-to-replicate)

**Unsupported in the proposed line:** "Humans and AI working together" matches their thesis. But "AI scientists propose, train and verify" and "a clinician sets the bar" describe your product, not their claims; nothing found says "propose, train and verify". "As Inherent Labs argues science should" turns a thesis about AI's promise into a claim about how science "should" be done, beyond the wording found. The line also implies endorsement.

**Corrected line:** Built at the SoTA Scientific Parallelism Hackathon, supported by Inherent Labs, whose stated view is that AI's promise lies "not in automating science, but in enabling a new kind of collective intelligence" of humans and machines. Here, AI agents search for the chip and a clinician sets the bar it must clear.

Backing quote: "AI’s promise lies not in automating science, but in enabling a new kind of collective intelligence" (https://inherentlabs.ai/)

**Do not claim:**

- That Inherent uses, endorses, partners with or favours ChipIn; the relationship is event support only.
- Kinship with Faraday or Replica results: their work is paper replication, not hardware or chip design, and all numbers are their own benchmark and judge.
- "Research taste" or "AI taste" for your agents unless you can show it; it is their research concept.
- That they say science "should" be done a particular way, or that AI "proposes, trains and verifies".
- That the product is self-improving or an AI scientist inventing across domains; those claims are theirs.

**Hard question they may ask:** "You say humans and AI work together, but is the AI actually doing science here, or is it a hyperparameter search? Where does a human add judgement beyond setting one threshold, and how do you know the winning design is a real discovery rather than a replication of a standard EEG classifier? Also, your verification is bit-exact against the model: does that show the model is right for seizures, or only that the gates match the model?"

**Name and logo rule:** Not found. No brand, press, logo or terms page on inherentlabs.ai (https://inherentlabs.ai/terms returned 404; the homepage has only a text wordmark). Use the name in plain text only, no logo, and ask them (curious@inherentlaboratories.com, shown on their homepage) or the organisers before using it.

**Not found:**

- Any public rule on using Inherent's name or logo.
- Any statement in their words that AI should "propose, train and verify".
- Any Inherent statement about hardware, chips, medical devices or EEG.
- Any statement that science "should" be done a given way.
- Interviews with direct quotes (not searched beyond their own pages).

## ARIA

**Who:** ARIA (Advanced Research and Invention Agency), the UK government R&D funding agency; it funds high-risk research, including the Scaling Compute programme (nearly 100m GBP, cheaper AI hardware inspired by nature) and AI for science. The Luma page uses only the acronym "ARIA". No line was proposed for ARIA, so the corrected line below is a draft.

**Their thesis:**

- "too speculative, too hard, or too interdisciplinary to pursue elsewhere" (https://www.aria.org.uk/about-us)
- "AI systems are beginning to generate hypotheses, design experiments, and, in some cases, execute them." (https://aria.org.uk/ai-in-science)
- "AI risks being applied incrementally rather than transforming how science is done." (https://aria.org.uk/ai-in-science)
- "Backed by nearly £100m, the Scaling Compute programme aims to address this challenge by rapidly shifting our current compute paradigm. Aiming to bring down the cost of AI hardware by >1,000x, the programme is funding pathways that take inspiration from natural processing systems" (https://aria.org.uk/media/nwffkeje/aria_corporate-plan_2026.pdf)

**Unsupported wording:** "backed by", "partnered with", "endorsed by", "funded by ARIA". The Luma page says only "supported by Callosum, Inherent Labs, ARIA and Fractile". ARIA's own pages do not mention the AI for Science Summit (only third-party listings do), and the Luma page lists the prize as "a demo slot at ARIA's 2026 AI for Science Summit", so the summit must not be presented as something the team has.

**Corrected line (draft):** Built at the Scientific Parallelism hackathon, an event supported by ARIA, whose work includes AI that "generate[s] hypotheses, design[s] experiments", and a programme aiming to cut AI hardware cost by more than 1,000x. ChipIn automates that loop for medical-sensing chips.

Backing quotes: "AI systems are beginning to generate hypotheses, design experiments, and, in some cases, execute them." (https://aria.org.uk/ai-in-science) and, for the event, "supported by Callosum, Inherent Labs, ARIA and Fractile" (https://luma.com/scientific-parallelism)

**Do not claim:**

- That ARIA funds, uses, endorses or partners with ChipIn, or that the team has a place at its summit (the demo slot is only the first prize).
- Kinship with Scaling Compute: it is about nature-inspired hardware to cut AI compute cost by >1,000x, not medical-sensing chips or weights-in-gates; ChipIn is not a funded ARIA performer.
- Kinship with Safeguarded AI or Mathematics for Safe AI, which concern a gatekeeper AI and guaranteed safety; bit-for-bit netlist verification is equivalence checking of one model, not a safety guarantee.
- ARIA's logo: use it only as ARIA allows; the funding brand guidelines are aimed at funding recipients, which the team is not.

**Hard question they may ask:** ARIA's own text warns that AI risks "being applied incrementally rather than transforming how science is done". The likely judge question is whether ChipIn changes how science or chip design is done, or only automates one narrow search loop. Related: beyond bit-exact equivalence to the model, how does the team show the EEG seizure alarm is clinically valid and meets the clinician-set bar, and how much smaller is the chip than a standard baseline?

**Name and logo rule:** Terms and Conditions (https://aria.org.uk/terms-and-conditions), section 7: "You must contact us for permission if you want to: say your website is associated with or endorsed by ARIA." Section 9: "ARIA's logo is also exempt from the OGL, except when it forms an integral part of a document or dataset", so the logo is not freely reusable. Funding brand guidelines (https://aria.org.uk/media/hdmlxfa2/aria-funding-guidelines.pdf): "DO NOT change the colour of the logo or tag line". Name ARIA in plain text as an event supporter, no logo, and ask ARIA for permission before using the logo or any wording that implies association.

**Not found:**

- Any ARIA-own-page statement about the AI for Science Summit on 26 Nov 2026 in Manchester; https://aria.org.uk/ai-in-science does not mention it, and only the third-party listing allai.events ties ARIA to Manchester on that date. The Luma page https://luma.com/edg3o5u2 says "powered by the Advanced Research + Invention Agency (ARIA)" with no date or venue.
- The Scaling Compute programme's own page (the guessed URL returned 404); the quotes come from the Corporate Plan 2026.
- The full text of the funding brand guidelines on name and logo permission (the PDF was only partly readable).
- Any ARIA statement about medical sensing, EEG, chip design for devices or fine-tuning at scale.
- Any interview with ARIA staff quoted directly on this topic (not searched).

This note responds to context/oran-notes/2026-11-21-sponsor-placements.md on the branch oran/context.
