# Team WhatsApp group (Parallelism Hack)

Source: the team's WhatsApp group "Parallelism Hack", 71 messages from 4 Nov
to 21 Nov 2026 (14:59), read read-only on 21 Nov 2026. A public copy is in
the sota-hack repo under `context/whatsapp/`.

## Planning before the event

- On 4 Nov the three (Adrian, Oran, Antonio) joked about the hackathon;
  Adrian said he would supply four Claude Ultra plans.
- On 17 Nov Oran asked whether the others were still keen and proposed a
  planning chat on Thursday. Adrian had a Friday deadline.
- The call was moved to Friday 20 Nov at 16:00 and all three agreed.

## Project brief posted by Oran (20 Nov, 16:39)

- The event: Scientific Parallelism, run by the Society for Technological
  Advancement in King's Cross, 21 to 22 Nov. Supported by Callosum, Inherent
  Labs, ARIA and Fractile. Teams get GPU environments, AI credits and mentors.
- Prizes: 5,000 pounds first (plus a demo slot at ARIA's AI for Science
  Summit in Manchester on 26 Nov), 2,500 second, 1,000 third. About 28 hours
  of build time. Team of three: one medical student, two engineers.
- Idea: a GPU-parallel search over the geometry of the arteriovenous graft
  anastomosis used for haemodialysis access, using a lattice Boltzmann solver
  to rank thousands of geometries by wall shear markers (TAWSS, OSI, RRT).
- Two levels of parallelism: per lattice node inside one simulation, and one
  independent simulation per geometry. The solver is memory-bandwidth-bound,
  so the story for sponsors is a roofline plot and fused collide-and-stream
  kernels (Fractile cares about data movement, Callosum about routing
  workloads across chips).
- Stretch goal: a small surrogate network trained on the geometry-to-shear
  sweep.
- Build order: CPU baseline, parametrised geometry (four or five
  parameters), one validated GPU run, batching, ranking, visuals.
- Limitations to state: shear predicts hyperplasia in direction, not
  magnitude; rigid walls and Newtonian blood; claim a design-screening tool,
  not patient prediction. Main risk: lattice Boltzmann with curved walls and
  a pulsatile inlet is a classic way to lose a weekend.
- The brief asks the receiving assistant to verify every figure and library
  before pitching.

## Adrian's reply (20 Nov, 16:45)

- Called it stronger than his own microfluidics idea, but raised three
  problems, none yet verified.
- First, ten thousand geometries may not fit: roughly 6 minutes per geometry
  gives about 900 GPU-hours, so aim for 500 to 2,000 until one run is timed.
- Second, the Reynolds number in a 6 mm graft is probably around 1,000 or
  more, which makes the flow unstable and the simple solver settings fragile.
- Third, there is no AI-for-science loop; the surrogate is only a stretch.

## Oran's follow-up on data (20 Nov, 16:50)

- The SimVascular Vascular Model Repository is real and open, but holds no
  dialysis access geometry. Idealised, parametrised geometry is the right
  tool for a design map anyway. svMorph may help perturb real geometry.
- Flow numbers: mature fistula 600 to 1200 ml/min; grafts 800 to 1200;
  measured mean 1186 plus or minus 588 ml/min; minimum graft diameter 6 mm.
  That gives Re around 1200 at the mean and about 1800 one standard deviation
  up, which is transitional.
- Waveform gap: no verified brachial inflow waveform. Options: a published
  Doppler waveform, a rescaled repository waveform, or the safe fallback of
  mean flow plus one 1.2 Hz sinusoid.
- Validate first on Poiseuille and Womersley flow, then against a repository
  geometry with reference solution. Blood: density about 1050 kg per cubic
  metre, viscosity 3.5 centipoise.
- Tonight's list: open a repository geometry, find a waveform within 15
  minutes, check svMorph installs, write parameter ranges with sources, and
  confirm the chosen LBM library runs a 3D test on the available hardware.
  Oran called that last item the one that decides whether the project happens.

## Event day, Saturday 21 Nov

- Oran had not got much done the night before; Antonio said they had enough
  to pitch and discuss a few ideas.
- The event really starts around noon; they agreed to arrive 11:45 to 12:00.
  Adrian asked Oran for a spot with chargers; Antonio added good WiFi.
- Oran arrived at 11:57, as the opening talk began. Adrian and Antonio were
  locked out at the door around 12:12; Oran said he would tell the organisers.
- Oran shared the schedule (relayed to an organiser, Luca). Saturday:
  arrivals and team formation 11:00-11:50, SoTA intro 11:50, sponsor talks
  from Callosum, Inherent and Fractile 12:00-12:30, lunch to 13:00, hacking
  13:00-18:00, dinner 18:00-19:00, hacking continues after 19:00.
- Sunday: breakfast 09:00, hacking 09:30-12:30, lunch to 13:00, final hacking
  and demo prep to 14:45, judges' briefing 14:45, demos and judging
  15:00-16:30, deliberation to 16:50, winners and close 16:50-17:00.
- Oran also posted two images at 12:51 (content not read).

## Links and notes shared

- Oran and Antonio shared several Granola meeting-note links (20 Nov 17:52,
  21 Nov 12:55 and 14:53) and Oran a Google Doc (20 Nov 19:05). Not opened
  here; they are private share links.
- Antonio pasted a list of past SoTA event projects (13:38), for example
  Trust Everything with ARIA in March 2026: MineTrust (mine clearing verified
  with zero-knowledge proofs) and ClawdBoat, later shown to BAE.
- Adrian shared the team repo on GitHub (14:59) and sent an invitation page.

## Antonio's alternative idea (21 Nov, 14:01)

- Hybrid computing study: biochip-inspired designs are expensive today but
  very power-efficient. Take existing hardware (GPUs, CPUs, data centres) and
  the biochip designs, find where they overlap, and ask where adding them to a
  hypothetical computer gives the best return.
- Framed as motivation a few years ahead, not designing chips: a constraint
  optimisation of a scarce, costly resource across existing systems.
- Antonio said he was explaining it mostly for a teammate, hence the length.

## Compute and credits

- Only mention: Adrian offering four Claude Ultra plans (4 Nov); the event
  itself provides GPU environments and AI credits.
