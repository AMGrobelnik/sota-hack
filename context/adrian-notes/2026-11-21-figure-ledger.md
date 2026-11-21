# SoTA hack: figure verification ledger

Checked 20 Nov 2026 against primary sources where reachable. Status key: VERIFIED (primary source read, matches), PARTLY (source exists, wording or scope differs), NOT FOUND (no primary source located; do not put on a slide), CHANGE (verified, but the brief's use of it is wrong).

## Clinical and cost

| Brief claim | Status | What the primary source says | Slide-safe wording |
|---|---|---|---|
| 1-yr primary unassisted patency 49% ePTFE, 62% AVF | NOT FOUND as a pair | Halbert et al. 2020, Kidney360 1(12):1437, ePTFE meta-analysis, 32 studies, 3381 grafts: 1-yr primary 41% (95% CI 35 to 47), primary-assisted 46%, secondary 70%. Huber et al. 2003, J Vasc Surg 38:1005: PTFE primary patency 33% at 18 months vs 51% autogenous. Almasri et al. 2016, J Vasc Surg 64:236: 2-yr primary 55% AVF vs 40% AVG. | "About 6 in 10 ePTFE grafts need an intervention within a year (pooled 1-yr primary patency 41%, Halbert 2020)." Note Halbert authors include Humacyte staff (competing graft maker); say so if asked. |
| $2.8bn Medicare vascular access, 2013, ~12% of ESRD payments | VERIFIED, CHANGE use | Thamer et al. 2018, AJKD 72(1):10, abstract: "in 2013, fee-for-service Medicare paid $2.8 billion for dialysis vascular access-related services, ∼12% of all end-stage renal disease payments." | Use as total access spend (FFS only, 2013, all access types incl. fistulae and catheters). It is not the geometry-addressable figure; that slice is unquantified. |
| $48.9bn Medicare dialysis spending 2022, ~7% of budget, <1% of beneficiaries | NOT FOUND | MedPAC July 2025 Data Book: ESRD group = 5.0% of Medicare spending and 1.0% of beneficiaries in 2022. USRDS spending chapter could not be read (JS-rendered). 7% matches an older FFS-only figure (2019, $37bn, "more than 7%"). | Drop, or use "ESRD is about 1% of Medicare beneficiaries and 5% of spending (MedPAC 2025 Data Book, 2022 data)". |

## Mechanism and flow

| Brief claim | Status | Source | Notes |
|---|---|---|---|
| 2025 IOP paper "Turbulence drives arteriovenous remodeling..." | VERIFIED exists | Varsanik et al., Phys Med Biol, DOI 10.1088/1361-6560/ae1ac8 (PMC12915627) | Mouse aortocaval fistula, CFD plus a two-rule agent-based model, validated against in vivo ultrasound. Not human, not a graft. Turbulence elevated at the juxta-anastomotic area. |
| Womersley 1.6, PI 0.42, Re 1817 mean, 2233 peak; "steady flow is sufficient" | PARTLY | Alam, Walsh & Newport 2022, Med Eng Phys 106:103834 | Re 1817 and 2233 confirmed. Wo and PI values not in the abstract; unverified. Rigid model, PIV, fistula not graft. Abstract wording is weaker than the brief: similar features "possibly owed to the low pulsatility index"; "the recirculation zone did not vary along the waveform". Say "an experimental study found steady and pulsatile flow gave similar features in a rigid AVF model". |
| Access flow mean 1186 ± 588 ml/min | VERIFIED, CHANGE use | PLOS ONE 2018, DOI 10.1371/journal.pone.0204630 | AVF patients, thermodilution (BTM) on the dialysis machine, range 166 to 3085. Fistulae, not grafts. Sampling grafts from it needs saying. |
| Mature AVF 600 to 1200 ml/min | PARTLY | Stated in vascular access reviews (Besarab review), secondary | Fine as context with a review cite. |
| Graft 800 to 1200 ml/min | NOT FOUND | Reviews say graft flow is "typically equal to or sometimes greater" than AVF at the same site | Drop the range. |
| KDOQI referral: <600, or <1000 with >25% drop over 4 months | PARTLY | Attributed to K/DOQI (2006) in a review, applies to fistulae and grafts | Check KDOQI 2006 primary text. The 2019 KDOQI update may not endorse flow surveillance; check before citing as current. |
| KDOQI 400 to 500 ml/min for fistulae | NOT FOUND | | Drop. |
| Rule of 6s (600 ml/min, 6 mm, <6 mm deep) | CHANGE | KDOQI-origin rule of thumb for fistula maturation | Not a graft parameter. Remove from the geometry rationale. |
| >1500 ml/min risks steal | PARTLY | No guideline cutoff. Reviews give "high flow" as 1500 to 2000+; steal reported at mean 1542 vs 1087 ml/min without steal | Say "high-flow access, conventionally above 1.5 to 2 l/min". Truncate the flow distribution accordingly. |
| Blood 1050 kg/m³, 3.5 cP, Newtonian | Convention, not checked | | Cite whichever CFD paper you align with. Williams 2021 used Bird-Carreau (shear-thinning). |
| Low WSS threshold | Source found, CHANGE use | Malek, Alper & Izumo 1999, JAMA 282:2035: <4 dyn/cm² (0.4 Pa) at atherosclerosis-prone arterial sites | Arterial atherosclerosis threshold. Veins have lower baseline WSS, so applying it to a venous anastomosis is open to challenge. Prefer the AVG-specific shear-rate thresholds used by Williams 2021 (read their methods). |

## Prior art

| Brief claim | Status | Source | Notes |
|---|---|---|---|
| 2024 AVG end-to-side CFD, 14.5 mm at 40° optimal | VERIFIED | Panganiban et al. 2024, Medicina 60(10):1704, DOI 10.3390/medicina60101704 | 9 configurations (3 diameters × 40/50/60°), Ansys Fluent teaching version, uniform 0.3 m/s inlet ("the default setting"), rigid walls, Reynolds stress turbulence model, no mesh convergence reported, unclear which vessel the diameters refer to. Describe factually: "nine configurations, no reported mesh convergence". |
| 2025 RADAR vs conventional | PARTLY | Wongchadakul et al. 2024, PLOS ONE, FSI study (PMC10791008). A 2025 CFD comparison was not dated in what I found. | RADAR is a fistula technique, not a graft. Low relevance. |
| US patent "Tailored venous anastomosis for arteriovenous grafts" | VERIFIED | US 11,369,381 B2, Washington University in St Louis; inventors Zayed, Williams, Genin, Leuthardt | Claims grooves at the venous end and anastomosis angle ≤30°. Legal status not checked. |
| HemeLB used for patient-specific AVF | VERIFIED | McCullough & Coveney 2021, Sci Rep, DOI 10.1038/s41598-021-01435-8 | AVF, not AVG. 50 µm lattice: 6.1M arterial + 16.8M venous sites; the 25 µm run took about 2.5 h on 1500 SuperMUC-NG nodes. Boundary conditions not checked. Useful scale comparison. |
| **Missing from the brief** | VERIFIED | Williams, Leuthardt, Genin & Zayed 2021, Sci Rep 11:12153, DOI 10.1038/s41598-021-90813-3 | Closest prior art. Idealised AVG, graft-to-vein angle 13° to 90°, transient, Bird-Carreau. <20° gives more pathologically low shear, >40° more high shear, ~30° optimal. Same group as the patent. |
| From the claude.ai chat | VERIFIED (abstract) | Lei, Archie & Kleinstreuer 1997, J Vasc Surg 25(4):637, DOI 10.1016/s0741-5214(97)70289-1 | Arterial bypass distal end-to-side, not AV. Iteratively optimised graft shape; WSS gradients cut to almost half vs standard and Taylor patch. Anastomosis shape optimisation is a 1997 idea, so never claim optimisation is new. |
| From the claude.ai chat | VERIFIED (abstract) | Applied Sciences (MDPI) 2025, 15(20):11064, DOI 10.3390/app152011064 | Helical AV grafts, 27 models (3 angles × 3 helical diameters × 3 pitches); best 25°, 13 mm, 30 mm pitch. Largest published grid found: 27 hand-picked points, 3 parameters. Positioning updated to "6 to 27 configurations". |
| **Missing from the brief** | Preprint | Wang, Abadie, Wall & Pérez Esteban 2025, arXiv 2508.06148 | Image-based AVG geometries; graft curvature (looped vs straight) dominates; looped grafts at 30 to 45° best on low WSS, high WSS and OSI. Not peer reviewed. |

## Williams et al. 2021 in detail (full text read, PMC8190231)

**Thresholds are wall shear RATE, not stress.**
- Pathologically low: γ̇ ≤ 50 s⁻¹. Cited rationale: fibrin deposition, coagulation (their refs 18, 22).
- Physiological: 50 to 1000 s⁻¹.
- Pathologically high: γ̇ ≥ 1000 s⁻¹. Cited rationale: wall micro-injury, platelet aggregation (refs 22, 23). Plots capped at 3000 s⁻¹.
- These are thrombosis-derived thresholds, not intimal hyperplasia thresholds. Say so if you adopt them.
- Stress equivalents at μ = 3.5 mPa·s (our Newtonian value): 50 s⁻¹ ≈ 0.18 Pa; 1000 s⁻¹ = 3.5 Pa.

**Metrics (their eqs 11, 12).**
- Γ_low = (γ̇_min / A₀) ∫_{S_low} (1/γ̇) dA, with γ̇_min = 1 s⁻¹, A₀ = whole model area, S_low = vein wall with γ̇ ≤ 50.
- Γ_high = (A₀ / γ̇_max) ∫_{S_high} γ̇ dA, with γ̇_max = 3000 s⁻¹, S_high = vein wall with γ̇ ≥ 1000.
- Problems: Γ_low's 1/γ̇ weighting blows up at stagnation and reattachment points, so one near-zero cell can dominate. Γ_high as printed has A₀ in the numerator, which gives units of area squared; almost certainly a typo for 1/(A₀ γ̇_max). Do not copy either literally.
- Recommendation: report area fraction of vein wall below 50 s⁻¹ and above 1000 s⁻¹ (time-averaged), plus their Γ_low with a floor on γ̇ if you want direct comparability.

**Set-up.**
- Brachio-axillary AVG. Artery 4 mm, vein 8 mm, graft tapered 4 mm (arterial) to 7 mm (venous), length 150 mm.
- Six angles only: 90, 60, 45, 30, 15, 13°, set via anastomosis major axis 7 to 30 mm.
- Vein 72 mm long, 25 mm distal to the graft.
- Pulsatile arterial inlet (8-term Fourier fit to brachial ultrasound), 700 ml/min into the graft, 90% graft / 10% distal artery split, constant 15 cm/s venous background flow. Outflow BCs. Rigid walls, laminar.
- Bird-Carreau blood: ρ 1060, μ∞ 0.0035 Pa·s, μ₀ 0.0056 Pa·s, λ 3.313 s, n 0.3568. The λ and n match the usual Cho and Kensey parameters, whose μ₀ is normally 0.056 Pa·s; the 0.0056 looks like a typo (moderate confidence, check their ref 35).
- Ansys Fluent, 200k to 250k elements, "refined until convergence" but no WSS convergence data shown.
- One cardiac cycle simulated (320 steps of 0.0025 s = 0.8 s), yet the text describes a "0.3 s heart beat". No cycle-to-cycle periodicity check reported.
- Re ≈ 1800 on 4 mm artery and 1.5 m/s peak.

**Their stated limitations are your parameters.** Flow held fixed, vein diameter not varied, rigid walls; "Future research will explore ... different axillary vein diameters." They also assert absolute vessel size should not change the optimum, untested. Your sweep tests it.

**Possible origin of the brief's 62%.** They quote AVG 1-yr primary patency 40 to 57% and secondary 62 to 78%. The brief's "62% for fistulae" may be a misread of graft secondary patency. Speculative.

**Validation target for us.** Reproduce their six-angle sweep at their geometry (4/7/8 mm, 700 ml/min). Differences to state: we run steady Newtonian, they ran pulsatile Bird-Carreau, so expect the trend (low-shear area rising below ~30°, high-shear rising above ~40°), not their numbers.

## Methods

| Claim | Status | Source |
|---|---|---|
| Initial design n ≈ 10d | VERIFIED | Loeppky, Sacks & Welch 2009, Technometrics 51(4):366, DOI 10.1198/TECH.2009.08040. Holds for "relatively uncomplicated" surfaces; examples d = 4 to 20. |

## Derived numbers (arithmetic, not sources)

- ν = 3.5 mPa·s / 1050 kg/m³ = 3.33e-6 m²/s.
- 6 mm, 1186 ml/min: mean velocity 0.70 m/s, Re ≈ 1260.
- 6 mm, 1774 ml/min (mean + 1 SD): velocity 1.05 m/s, Re ≈ 1880. The brief's "~1800" is slightly low.

## What this changes in the pitch

1. Positioning: Williams 2021 already swept one parameter (angle) and found an optimum. Claim becomes: "published work sweeps one parameter at a time, about ten configurations per study; we search a five-parameter space with a learned surrogate."
2. Validation gift: slice your surrogate along the angle axis and check whether it reproduces a ~30° optimum under comparable conditions. Agreement is a strong credibility slide; disagreement must be explained before a judge finds it.
3. Objective thresholds: take the AVG-specific shear thresholds from Williams 2021 rather than the arterial 0.4 Pa.
4. Patency: use 41% (Halbert 2020), not 49%/62%.
5. Money: $2.8bn is total access spend, not geometry-addressable. Drop $48.9bn.
