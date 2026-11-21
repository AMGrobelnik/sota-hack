# Feedback on round 1 of the landing pages and dashboards (Sat 21 Nov, about 17:10 to 17:40)

Paraphrased from the team chat and from Adrian. Round 1: five landing variants and five dashboard variants.

## Landing pages

- Liked: the exploded, CAD-like break-apart on scroll (variant 1); the rotating chip of variant 2 (best animation); zooming into the device and the chapter rail on the right (variant 3); the breakdown of the chip's parts (variant 4).
- More detail and more photorealistic 3D; the logic gates looked fake.
- No slogan printed on the chip itself.
- Variant 2 is too long to scroll.
- Graphs more visual and moving; the training graph easier to understand.
- Medical devices in general, not only wearables; a device or machine, possibly partly transparent, zooming from the outside view to the inside, down to logic gates and binary.
- Scene idea: many rooms, each a real setting of a medical device; zoom into one room, then the device, then split it apart, then the breakdown of its parts.
- The many-chips image belongs at the end, as all the chips made, each labelled with a medical device it could power.
- Do not focus on the specific use cases: the product is the AI scientist environment.
- No mention of GitHub. The people section is called About and shows all three photos.
- No suggested prompts on a chat interface.
- Asked for: ten more variants using all of this.

## Dashboards

- Round 1 had far too much on screen.
- Build it like AI Inventor with mock data: a sidebar with runs, a start page where you write the prompt and start, a run that is currently in progress to click through.
- Spare by design, usable by the simplest user; the power sits in menus and settings.
- Three views: Overview, Chat, Visual.
- Keep views that are useful for this specific domain (medical sensing chips).
- Asked for: five more variants.

## Dashboards, round 2 walk-through (Sat 21 Nov, about 18:25)

Paraphrased from a teammate's spoken walk-through of the round-2 dashboards.

- Show which datasets are being loaded and from where, and which papers the scientists use; a clinician wants to know the source of the data.
- Fine-tuning needs a better animation: many candidate models narrowing to the best one, with the gates.
- Show a visual concept of the device: a mannequin wearing a prototype, and the chip.
- The Visual view looked amateur: make it 3D and animated; say explicitly what Sensor 1 and Sensor 2 are; show what is fine-tuned or let the user choose to fine-tune.
- Signal should read continuously; the sensors that are reading should light up.
- Trade-off: make the candidate chip obvious.
- Text colour blends into the background on every tab: more contrast.
- "On the device" looked vague: make it look like a real chip.
- Start page: keep the Lite, Pro, Max, Ultra choice and the GPU choice; the use-case choice was not understood.
- After the prompt the product should ask questions: own dataset, yes or no; if no, look for a public dataset and use it; if none, ask permission to simulate one, state the assumptions and why, and let the clinician confirm or correct them.
- Asked for: five more dashboard variants using this.

## Waitlist, next iteration (Sat 21 Nov, about 19:10)

From Adrian; to be done together with the next round of landing page variants, not before (more feedback is coming first).

- The site now runs on the domain chipin.space; the waitlist landing page is at /waitlist.
- Show "N people on the waitlist" on the page, with a made-up number for now.
- Add a world map of the countries people signed up from, with mock countries for now.
- Open point: swap the made-up number and countries for the real ones from the store before the page is sent out.

## Dashboards, late feedback on round 2 (Sat 21 Nov, about 19:45)

Paraphrased from the team; applied to the round-3 dashboards.

- Next to the big gate count, show how much smaller the chip is than what is typically needed.
- Under the details, show how the gate count came down from round 1 to round 4.
- Make the chip look live: current flowing from Sensor 1 and Sensor 2 through the chip.
- Give the work a voice, as if one person were checking all the models at once ("Chipmonk is checking ...").
- The small chip at the top right and the chip drawing of round-2 variant 5 were liked.
- The signal should be a live feed.

## Landing pages, round 2 feedback (Sat 21 Nov, about 19:50)

Paraphrased from the team; asked for: five round-3 variants.

- The view of many hospital rooms is liked; make it real: a newborn in the incubator, a patient on the operating table, a dialysis patient with the line in the arm, an intensive-care patient with an oxygen mask, someone at home.
- Let the visitor click any room to zoom into it and on to its chip.
- Bedside monitors: real readings (heart rate, oxygen saturation, respiration, blood pressure); they were too bright and looked fake.
- Focus on the chip, bold and clear; no tour of the device parts; never cut the chip in half; no shelf of devices.
- Current flowing through the sensor inputs and the chip is liked; make it smoother and more real.
- A smaller zoom step from the fine-tuned model to the gates; the four transistors clearer; a smoother move from the gates to one chip per device.
- Make it obvious that each chip is a different chip for a different device.
- Remove: the model-matches-chip chapter, the small sensor/weights/gates/prediction panel, unexplained blue highlight boxes, the NAND and AND animation, labels crossed by a line.
- Charts: put the explanation above or beside the graph; make the "good enough" line clear, perhaps adjustable.
- Liked: example prompts typing themselves, the workflow row at the top, the run shown at the side (and where the training data comes from), the swarm of thousands of designs, the hospital from outside, "Build the next chip" and "Smaller, then smaller", the gate close-ups.
- Say why a smaller chip matters.
- Idea: show numbers on how many medical devices are built each year (only sourced figures are to be used).
- Planned as well: a "How it works" page.

## Product name and repo layout (Sat 21 Nov, evening)

- The platform is called ChipIn (capital C, capital I, one word); the domain is chipin.space.
- Pages already published keep the earlier name; every new variant uses ChipIn.
- The logo is undecided: several logo options are to be tried and the team picks.
- The interface lives on the branch amg/frontend and the backend on the branch amg/backend; they are not connected yet.
- The backend is a trimmed copy of the AI Inventor backend: OpenRouter access (also used for summarising, as in AI Inventor; no free-model handling), the Claude agent backend, and runs on the Mac and on RunPod (on demand and flex). Only the parts that are needed go into the public repo.
