# Decisions (Sun 22 Nov)

Paraphrased from the team's walk-through and from Adrian.

## Landing page

- Base: round-4 variant 1, "The full descent" (variants/y1.html), as the single base. The next round is one page, not five.
- First, a speed pass: no blur, no reduced quality; before and after pictures must match.
- Then the walk-through feedback:
  - Fix the flicker in the logic-gates chapter and calm it.
  - Explore only one room in detail (intensive care).
  - The ending still shows a different chip in every device; each tells its purpose when clicked.
  - The loop's dot runs between the boxes, and each box fills like light.
  - A "Try now" button where the 3D story ends.
  - Smooth pass from monitor into chip as in variant 4, and its light shafts if they cost no speed.
  - No blown-out glow.
  - A slot for a dashboard screenshot in the first pitch card (to become a screen recording).
  - The waitlist, About and closing sections stay as they are.
  - All copy in one marked place, so the words can be edited next.
- Candidate address when built: variants/z2.html (speed-only copy: variants/z1.html).
- Variant 5 was rejected. The how-it-works page is unchanged until its content arrives.

## Backend and chip lab layout

- Option 1 now. Nothing moves.
- The backend (branch amg/backend-chiplab) reaches the lab through the `chiplab` command.
  - CHIPIN_CHIPLAB_BIN points at the existing lab install's bin folder.
  - CHIPLAB_CONFIG and CHIPLAB_USER_DIR are set when the install is outside the defaults.
- End-to-end test: lab commit 5b15d6c and examples/seizure_eeg_prompt.md.
  - Evidence: compile and verify stages, lab metrics and chips/ artifacts in events.jsonl.
  - The report goes to m3/e2e/REPORT.md, with a pull request into ant/chip-lab.
  - If it passes, amg/backend-chiplab is merged into amg/backend.
- Option 2 follows once the run is green: amg/backend and ant/chip-lab merged into main with normal merge commits. The lab owner agrees to it then.
- The lab's tools are never installed into a real home folder on the demo machine; they stay inside the project folder.

## Agent backends

- Claude or OpenRouter.
- The Inkling 2 models are used through OpenRouter (presets inkling-mini, inkling-small). No Tinker key is needed.

## Dashboards

- Round 5 has five variants live under dashboard/ (h1 to h5).
- Round 4 is kept under dashboard/round4/. Work on round 4 stopped when round 5 started.

## Demo roles

From the team's walk-through, to be confirmed by the team.

- One member presents the clinical side and walks through the dashboard.
- The other two split the technical part (the chip and how it is made).
