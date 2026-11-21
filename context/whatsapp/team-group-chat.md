Parallelism Hack (WhatsApp group), 2026-11-04 to 2026-11-21, 71 messages, exported read-only on Sat 21 Nov 2026

2026-11-04 18:43  Antonio: Two people with a 100% win rate, crazy
2026-11-04 19:01  Adrian: If it goes wrong we blame you.
2026-11-04 19:01  Antonio: Dude, you’re so cracked how could it ever go wrong?
2026-11-04 19:02  Antonio: You’ll carry us for the win fr
2026-11-04 19:03  Adrian: Nah it'll be Oran, I'll just provide the 4 claude ultra plans, and you can steal all the food
2026-11-04 19:04  Oran: Booommmmm
2026-11-17 16:43  Oran: You guys still keen on doing this
2026-11-17 16:44  Oran: If so lets chat on Thurs about plan
2026-11-17 16:46  Adrian: Yep. Got a deadline Friday, chat Thursday anytime after 3?
2026-11-17 16:47  Adrian: [image] We can also meet at this event
2026-11-17 16:47  Adrian: [image] We can also meet at this event
2026-11-17 16:48  Oran: You going to Oxford?
2026-11-17 16:48  Adrian: Nevermind lool (edited)
2026-11-17 16:49  Oran: Was planning on going to London on Friday anyway
2026-11-17 16:49  Adrian: Changed location yesterday
2026-11-17 16:49  Oran: Friday also works for me if easier
2026-11-17 16:49  Adrian: U planning to go evening ye?
2026-11-17 16:50  Oran: To London?
2026-11-17 16:50  Oran: If so was gonna go during the day so i can see family
2026-11-17 16:51  Oran: But also have an open ticket so can head anytime
2026-11-17 17:00  Adrian: Fair enough, I'll try make time to meet on Thursday then. we'll see what antonio says
2026-11-18 04:27  Antonio: Anytime works except this afternoon.
2026-11-19 12:33  Adrian: cant do today, lets call friday anytime after 3?
2026-11-19 12:37  Oran: Sweet
2026-11-20 13:52  Oran: Call at 4?
2026-11-20 14:07  Antonio: Sounds good on my side
2026-11-20 14:12  Adrian: agreed
2026-11-20 16:39  Oran: Context for you, the assistant receiving this. This is a hackathon project brief. The event is “Scientific Parallelism”, run by the Society for Technological Advancement in King’s Cross, London, 21 to 22 November 2026, supported by Callosum, Inherent Labs, ARIA and Fractile. The central question teams answer is: which scientific questions could we investigate better if computation were faster or could run at greater scale? Teams get GPU environments, AI credits and mentors. Prizes are £5,000 first (plus a demo slot at ARIA’s AI for Science Summit in Manchester on 26 November), £2,500 second, £1,000 third. Build time is roughly 28 hours. Team is three people: one medical student doing the idea, framing and pitch, and two capable engineers.
    The project in one sentence. Build a GPU-parallel search over the geometry of the arteriovenous graft anastomosis used for haemodialysis access, simulating pulsatile blood flow through thousands of candidate geometries at once and ranking them by the haemodynamic markers associated with graft failure.
    The clinical problem. Patients with end-stage kidney disease need high-flow vascular access for haemodialysis three to five times a week. Where native vessels are inadequate for an arteriovenous fistula, surgeons implant a synthetic conduit (usually ePTFE) joining an artery to a vein: an arteriovenous graft, or AVG. These fail, predominantly by stenosis at the venous anastomosis caused by intimal hyperplasia. One-year primary unassisted patency has been reported at 49% for ePTFE AVGs and 62% for fistulae. Separately, 30% to 70% of fistulae suffer primary failure and never mature into usable access.
    The money. US fee-for-service Medicare paid approximately $2.8 billion for dialysis vascular access-related services in 2013, around 12% of all end-stage renal disease payments. Total Medicare dialysis spending was $48.9 billion in 2022, about 7% of the programme’s budget for under 1% of beneficiaries. Note: these are US payer figures and should be re-verified against the current USRDS Annual Data Report before use in a pitch.
    The mechanism, and why geometry matters. Regions of low and oscillatory wall shear stress at an anastomosis are associated with intimal hyperplasia. This link is long established in the vascular literature, including in vivo graft studies, and is specifically documented at the venous anastomotic side of AV grafts on histology. The flow field at the join is determined by the geometry of the join: graft-to-vein angle, diameter ratio, planar versus out-of-plane approach, and the shape of the heel and toe. Surgeons select this geometry by hand and convention.
    The gap. Geometric optimisation of anastomoses has been attempted since the 1990s. A 1997 Journal of Vascular Surgery study showed an optimised end-to-side geometry could roughly halve wall shear stress gradients compared with a standard anastomosis and with the Taylor patch. But published studies compare small numbers of designs because each simulation is expensive: a 2025 CFD study of helical graft designs analysed twenty-seven models across anastomosis angle, helical diameter and helical pitch. Nobody has searched the space exhaustively. The constraint is compute.
    Why this is a parallel computing project, specifically. Two nested levels of parallelism:
    Inner level. Use the lattice Boltzmann method (LBM) as the flow solver. The domain is a 3D lattice; each node stores around 19 (D3Q19) or 27 (D3Q27) distribution functions. Each timestep is collide (local arithmetic at a node) then stream (copy to immediate neighbours). No non-local dependencies, so every lattice node updates independently. A geometry with millions of nodes yields millions of independent work units per timestep. This is canonical GPU data parallelism.
    Outer level. Each candidate geometry is a fully independent simulation with no inter-simulation communication. Embarrassingly parallel across thousands of geometries.
    Why it is genuinely expensive. The relevant metrics (time-averaged wall shear stress TAWSS, oscillatory shear index OSI, relative residence time RRT) are defined as averages over the cardiac cycle, so steady-flow shortcuts are invalid. Each geometry needs several full pulsatile cycles, i.e. thousands of timesteps.
    The sponsor-relevant technical angle. LBM is memory-bandwidth-bound, not compute-bound. Per node per timestep it reads roughly 19 values, writes 19, and performs on the order of 100 floating-point operations, giving an arithmetic intensity near 1 flop per byte, an order of magnitude below the point at which a modern GPU becomes compute-limited. The optimisation work is therefore about data movement: fusing collide and stream into a single pass, and choosing a memory layout (structure-of-arrays, and a push versus pull streaming scheme) that keeps neighbour access coalesced. Produce a roofline plot showing the kernel sitting on the bandwidth ceiling. This matters because sponsor Fractile builds in-memory-compute inference chips premised on the energy and latency cost of moving data between compute and memory, and sponsor Callosum builds software to route workloads across heterogeneous chip types.
    Stretch goal with a genuine hardware story. Train a small surrogate network on the geometry-to-shear-field dataset the sweep produces, so new geometries score in milliseconds. This turns the system into expensive physics run in parallel once, then cheap neural inference thereafter. Two stages wanting different silicon. Treat as stretch, not core.
    What to actually build, in order.
    Measure a CPU baseline for a single pulsatile simulation on one geometry before optimising anything. The speedup claim depends on this and it must be measured, not estimated.
    Parameterise an idealised AVG venous anastomosis (angle, diameter ratio, out-of-plane offset, heel/toe radius). Keep it to four or five parameters.
    Get one GPU LBM simulation running correctly on one geometry with pulsatile inlet and validate against a known case (Poiseuille flow in a straight tube, or a published benchmark).
    Batch across geometries.
    Compute TAWSS, OSI, RRT per geometry and rank.
    Build the visual: shear maps, a ranked leaderboard, and a parameter-space plot showing which regions of design space are favourable.
    Tooling, with confidence levels. JAX-based and PyTorch-based LBM implementations exist (search “XLB lattice Boltzmann JAX” and “lettuce PyTorch lattice Boltzmann”); I have not verified their current state and the team should check before committing. Palabos and waLBerla are established LBM codes suitable for a baseline. SimVascular maintains an open repository of patient-derived vascular geometries (search “SimVascular Vascular Model Repository”) but idealised parameterised geometries built from published dimensions are sufficient for a method demonstration and carry less setup risk. Do not rely on any dataset or library in this brief without checking it exists and works.
    Honest limitations to state rather than hide.
    Wall shear stress predicts intimal hyperplasia in direction but not reliably in magnitude. Patient vascular quality, surgical technique, cannulation practice and systemic factors are substantial contributors.
    Bioincompatibility at the ePTFE interface is also implicated in intimal hyperplasia and is a materials problem geometry cannot address.
    Rigid-wall assumptions, Newtonian blood rheology and idealised geometry all limit the result. Vessel wall deformation has been shown to change the haemodynamics materially.
    Therefore the defensible claim is a design-screening tool for device geometry, not a prediction of patency for an individual patient. Do not claim recoverable healthcare savings; quantifying the geometry-attributable fraction would require a trial.
    The pitch framing. “Half of synthetic dialysis grafts need an intervention within a year, and they fail at one specific place: the venous anastomosis, where intimal hyperplasia narrows the join. Medicare alone spends around $2.8 billion a year keeping dialysis access working, roughly 12% of everything it spends on kidney failure. The geometry of that join is one determinant and is currently chosen by hand. Published computational studies compare tens of candidate geometries. We searched ten thousand.”
    Main risk of failure. A lattice Boltzmann implementation with correct curved-wall boundary conditions and a pulsatile inlet is the classic way to lose a weekend. If neither engineer has written a stencil or LBM kernel before, this project is high risk and a simpler alternative should be chosen instead.
    What the receiving assistant should do. Verify every figure and every library named above against primary sources before any of it goes into a pitch; several are cited from secondary summaries. Flag anything that does not check out. Then help with implementation, validation strategy, and the roofline analysis.
2026-11-20 16:45  Adrian: It is a strong idea and better than my microfluidics one, but as written it has three problems to fix before you commit. Nothing below is verified yet: three agents are now checking every figure, the novelty claim and the tooling against primary sources, as the brief asks.
    What is good
    - Real problem, clear gap: a specific device fails at a specific place, and the pitch line "published studies compare tens, we searched thousands" is easy to grasp.
    - Fits three of your four constraints: hardware (a physical implant being designed), biotech and medicine, and a visual demo (shear maps and a leaderboard).
    - Honest scope: it claims a design-screening tool, not patient outcomes, which is what a sceptical judge will accept.
    Problems
    1. Ten thousand may not fit in the weekend. My rough estimate is about 6 minutes per geometry on one GPU, so 10,000 would need around 900 GPU-hours and 1,000 around 90.
    - Assumptions: 3 million lattice nodes, 225,000 time steps for three heartbeats, 2 billion node updates per second.
    - Treat the headline as 500 to 2,000 until one run is timed. That is still 20 to 70 times the 27 in the cited study.
    2. The flow is probably not smooth. By my estimate the Reynolds number in a 6 mm graft at dialysis flow rates is around 1,000 or more, where flow starts to become unstable. The simplest solver settings can blow up there, and shear at the wall becomes sensitive to resolution.
    3. There is no AI-for-science loop, which was one of your constraints. The core is a brute-force sweep, with the neural surrogate only as a stretch goal.
2026-11-20 16:50  Oran: Short answer: yes for flow, yes for validation, no for dialysis-specific patient geometry. And the missing one turns out not to matter, for a reason worth understanding.
    Geometry: the repository is real, but it has no dialysis access
    The Vascular Model Repository exists and is open. It is a library of computational models of normal and diseased human cardiovascular and pulmonary anatomy, with input and output boundary conditions for various physiologic states, and it was built partly so that researchers can verify their computational methods against spatially and temporally resolved benchmark solutions. One paper using it describes 72 geometries freely available as curated SimVascular projects. 
    stanford
    arxiv
    But look at what is actually in it: cerebrovascular, pulmonary arteries in Fontan patients, left circumflex coronary artery, aortic coarctation including end-to-end anastomosis, abdominal aortic aneurysms, coronary aneurysms in Kawasaki patients, superior vena cava and pulmonary arteries in Glenn patients, and aortoiliac occlusive disease. 
    arxiv
    No arteriovenous fistula. No dialysis graft. There is an aortic coarctation end-to-end anastomosis, which is an anastomosis of a sort, but it is not yours.
    I did not find an open repository of segmented dialysis access anatomy. If one exists I have not located it, and you should not plan tomorrow around finding one tonight.
    Why that gap is actually fine, and arguably helpful
    Patient-specific geometry is the wrong tool for what you are building.
    A patient-specific simulation answers “will this individual’s graft fail?”. A design-space map answers “which geometric configurations produce favourable haemodynamics?”. For the second question, real patient anatomy is a liability, because every patient differs along dozens of uncontrolled dimensions at once. You could not attribute a difference in shear to the angle you varied.
    What a design map needs is idealised geometry with parameters you control, which you generate yourself. That is standard practice in this literature: the studies you are extending used idealised geometries precisely so the parameters were separable.
    So build the geometry in code. Four or five parameters: graft-to-vein angle, diameter ratio, out-of-plane offset, heel and toe radius. That is an evening’s work with a mesh library and it is scientifically the correct choice, not a compromise.
    One useful find: SimVascular ships svMorph, described as a research tool for in-silico morphological editing of patient-specific vascular geometries. If you do want to perturb a real geometry rather than build from scratch, that is the tool. Worth ten minutes tonight to see if it is usable. 
    github
    Flow data: this is the strong part
    You have unusually good numbers here, because dialysis access flow is measured routinely in clinic as part of surveillance.
    Quantity	Value	Source
    Mature AVF flow	typically 600 to 1200 ml/min	arXiv 2023
    Prosthetic graft flow	800 to 1,200 ml/min	Endovascular Today
    Measured distribution	mean 1186 ± 588 ml/min	J Vasc Access study
    Referral threshold	absolute 600 ml/min, or below 1000 ml/min having dropped more than 25% over 4 months	KDOQI
    Standard graft diameter	minimum 6 mm, per KDOQI’s “6s rule”	KDOQI
    Upper bound of interest	above 1500 ml/min risks distal ischaemia, steal syndrome	arXiv 2023 
    Deep denoising autoencoder-based non-invasive blood flow detection for arteriovenous fistula
    +4
    That mean and standard deviation is the useful one. You can sample flow rates from a real measured distribution rather than picking a round number, which makes your sweep a population sweep rather than a parameter guess.
    It also pins down your Reynolds numbers. At 6 mm and 1186 ml/min you get a mean velocity around 70 cm/s and Re around 1200. At one standard deviation above the mean, Re is roughly 1800, and systolic peak takes it higher. So my earlier caution was right: the top of the clinically real range is genuinely transitional. Keep your validated point near the lower end.
    And a physiological simplification in your favour. A mature access has a low-pitched continuous bruit. Continuous, not systolic-only. Because the venous outflow is a low-resistance bed, flow does not drop to near zero in diastole the way it does in a coronary or a limb artery. Your waveform is therefore high mean flow with relatively modest pulsatility, which is both easier to prescribe and numerically gentler than a coronary waveform. 
    arxiv
    The one genuine gap
    An inlet velocity waveform for the artery feeding the access. I have not verified an open, citable brachial or radial artery waveform for the dialysis context, and I am not going to give you one from memory.
    Three ways to close it tonight, in order of preference:
    Search for a published brachial artery Doppler waveform in AVF patients. Terms: “brachial artery velocity waveform arteriovenous fistula Doppler”, “AVF inflow waveform CFD boundary condition”. There is a CFD-of-AVF literature and those papers must state their inlet condition. Lift it with a citation.
    Take a waveform from the Vascular Model Repository, since it includes input and output boundary conditions for various physiologic states, and rescale it to your mean flow. Say that you did. 
    stanford
    Prescribe a simple analytic waveform: steady mean flow plus a single sinusoidal harmonic at 1.2 Hz, amplitude set to a stated pulsatility index. Defensible for a design study as long as you state it and run a sensitivity check.
    Option 3 is the safe fallback and costs nothing. Do not let this block the build.
    Validation data, which matters more than geometry
    This is where the repository earns its place. It exists so that researchers can verify computational methods against benchmark solutions, and its simulations were run with rigid walls, Windkessel or resistance outlet boundary conditions, and a prescribed time-varying parabolic inflow, which is exactly the setup you will use. So you can take one of its geometries, run your solver on it, and compare against a published reference solution. 
    stanford
    arxiv
    Also validate against analytic solutions first, because they are free and unarguable: steady Poiseuille flow in a straight tube, then Womersley flow for the pulsatile case. If your solver reproduces the Womersley velocity profile, your pulsatile implementation is correct. Do that before anything else on Saturday morning.
    Blood properties
    Standard literature values, state them explicitly: density around 1050 kg/m³, dynamic viscosity 3.5 centipoise for a Newtonian assumption. Note in your limitations that blood is shear-thinning and that the Newtonian assumption is most defensible at the high shear rates found in a dialysis access, which is a point in your favour here and against you in the coronary regime.
    Tonight’s shopping list
    Download the Vascular Model Repository and confirm at least one geometry plus its reference solution opens.
    Find one citable inflow waveform, or decide on the analytic fallback. Fifteen minutes, then stop.
    Check svMorph installs, in case you want morphological perturbation.
    Write down your parameter ranges with sources: 6 mm diameter, flow sampled from 1186 ± 588 ml/min, angle range from the published anastomosis studies.
    Confirm your LBM library of choice actually runs a 3D test case on the hardware you will have.
    Item 5 is the one that decides whether this project happens. Do it first.
2026-11-20 17:51  Oran: Can u send granola
2026-11-20 17:52  Antonio: [removed]
2026-11-20 19:05  Oran: [removed]
2026-11-21 09:11  Oran: What we saying boys
2026-11-21 09:11  Oran: Was low key tweaking last night so didn’t get much done
2026-11-21 09:18  Antonio: Nah don’t worry, we have enough to pitch/discuss a few ideas
2026-11-21 09:49  Oran: What time y boys getting there
2026-11-21 09:49  Oran: Cause just looked and it only really starts at around 12
2026-11-21 09:50  Antonio: Oh shi, we can do some time between 11:45-12 then?
2026-11-21 09:50  Antonio: We haven’t left yet so still flexible
2026-11-21 09:50  Oran: Ye sweet let’s do that
2026-11-21 09:50  Antonio: Perfect, see you soon
2026-11-21 11:06  Oran: ETA?
2026-11-21 11:21  Antonio: 12
2026-11-21 11:30  Adrian: Get us a good spot w chargers if you're early🙏🏿
2026-11-21 11:30  Antonio: Good WiFi
2026-11-21 11:34  Oran: Not there yet
2026-11-21 11:34  Oran: Probs getting in same time as u lot
2026-11-21 11:57  Oran: Am here btw
2026-11-21 11:57  Oran: Talk is about to start
2026-11-21 12:01  Antonio: Within 10 min aaaa
2026-11-21 12:05  Oran: I’ve got granola on dw
2026-11-21 12:12  Adrian: Tell someone we infront the door outside
2026-11-21 12:12  Oran: It should just open
2026-11-21 12:12  Oran: The door on the right
2026-11-21 12:13  Adrian: No
2026-11-21 12:13  Oran: Also can’t really as in the middle of talk
2026-11-21 12:13  Adrian: [image]
2026-11-21 12:13  Adrian: [image]
2026-11-21 12:13  Oran: Does it not open
2026-11-21 12:13  Adrian: No
2026-11-21 12:13  Oran: I’ll try tell them one sec
2026-11-21 12:51  Oran: [image]
2026-11-21 12:51  Oran: [image]
2026-11-21 12:55  Oran: Hi Luca, please see below 🙂 
    **Saturday**  
    11:00–11:50 · Arrivals, check-in and team formation  
    11:50–12:00 · SoTA introduction  
    12:00–12:30 · Talks from Callosum, Inherent and Fractile  
    12:30–13:00 · Lunch  
    13:00–18:00 · Hacking 
    18:00–19:00 · Dinner  
    19:00 onwards · Hacking continues  
    **Sunday**
    09:00–09:30 · Breakfast  
    09:30–12:30 · Hacking 
    12:30–13:00 · Lunch  
    13:00–14:45 · Final hacking, testing and demo preparation  
    14:45–15:00 · Judges’ briefing and demo setup  
    15:00–16:30 · Team demos and judging  
    16:30–16:50 · Judges’ deliberation  
    16:50–17:00 · Winner announcements, prizes and closing
2026-11-21 12:55  Oran: [removed]
2026-11-21 13:38  Antonio: Trust Everything (with ARIA, Mar 2026)	MineTrust: autonomous mine clearing, verified with zero-knowledge proofs	Tech Excellence: ClawdBoat (later presented to BAE)	Alex Obadia (ARIA Programme Director), Nicola Greco, Awais Rashid, Jamie
2026-11-21 14:01  Antonio: So the idea is that there's things that are being done for biochip design using cells and so on to be more efficient circuits for chips and so on, and sort of any computational circuit. So on one hand, you have that. On the other hand, you have all the existing hardware that currently exists. So GPUs, CPUs, computers, data centers, and so on, right? And there's a gap here, right? Currently, the bio stuff is too expensive to make, and probably it's going to become important very soon. On the other hand, you have so many different opportunities and places you could add it into real hardware, right? But you can't add it into everything because it's too expensive, but it does have some advantages like power, being very power efficient and so on. So what we can do is we can take all existing hardware that exists, we can take all the biological, biochip-inspired designs and things that exist, and we see where the overlap is. So we can start designing systems like a hypothetical computer, for instance, and we think about, okay, if we would add these biochips or biochip-inspired designs with their advantages into the computer, where does it make the most sense to add it in? I'm saying this more to him, not to you. That's why I'm being lengthy. So we need this as a hybrid system. And the idea is to motivate, right? So we're not going to design these things. We're thinking like a few years ahead when these things will actually be able to be designed, right? They'll still be very expensive, but at that point, it's important to realize where the opportunities are, where the highest ROI is in implementing this software into real computer systems. So in another sense, this is a sort of constraint optimization problem where you have a limited amount of these resources, they cost way more, but you want to add them into existing systems for maximum ROI. Yeah.
2026-11-21 14:53  Antonio: [removed]
2026-11-21 14:59  Adrian: https://github.com/AMGrobelnik/sota-hack
2026-11-21 14:59  Adrian: [removed]
