# Dialysis graft geometry sweep

The idea Antonio brought to the team call on 20 Nov, written up as a
project brief, then fact-checked. Adrian pasted two texts on 20 Nov:
the brief itself (summarised below) and another assistant's answer on
data availability (the follow-up note below). That answer's verdict:
flow data yes, validation cases yes, dialysis-specific patient
geometry no, which matters little because a design map uses idealised
shapes built in code. Raw fact-check:
[data/dialysis-graft-verification.json](data/dialysis-graft-verification.json).

## The brief, in summary

**One sentence.** A GPU-parallel search over the shape of the join
(anastomosis) between a synthetic dialysis graft and a vein,
simulating pulsing blood flow through thousands of candidate shapes
at once and ranking them by flow markers linked to graft failure.

**Clinical problem.** People with kidney failure need high-flow
access to their blood for dialysis. When their own vessels will not
do, surgeons sew in a plastic tube (usually ePTFE) from an artery to a
vein: an arteriovenous graft (AVG). These grafts mostly fail by
narrowing where they join the vein, from scar-like overgrowth of the
vessel lining (intimal hyperplasia).

**Mechanism.** Low and back-and-forth (oscillatory) shear stress on
the vessel wall is associated with that overgrowth. The join's shape
(angle, diameter ratio, in-plane or out-of-plane approach, heel and
toe shape) sets the flow, and surgeons choose it by hand and habit.

**Gap.** Shape optimisation of joins goes back to the 1990s, but each
simulation is expensive, so studies compare tens of designs. The
brief's claim: nobody has searched the space exhaustively.

**Why parallel.** Two levels. Inside one simulation, lattice
Boltzmann (LBM) updates every grid point independently each step.
Across simulations, every candidate shape is independent. The wall
metrics are averages over the heartbeat: time-averaged wall shear
stress (TAWSS), oscillatory shear index (OSI) and relative residence
time (RRT), so each shape needs several full pulsing cycles.

**Sponsor angle.** LBM is limited by memory bandwidth, not
arithmetic, so the work is about data movement: fuse the two update
steps, choose a memory layout, and show a roofline plot with the
kernel on the bandwidth ceiling. That speaks to Fractile (data
movement) and Callosum (routing work across chip types). Stretch: a
small neural surrogate trained on the sweep scores new shapes in
milliseconds.

**Build order.**

1. Measure a CPU baseline for one pulsing simulation first.
2. Parameterise an idealised join with four or five parameters.
3. Get one GPU LBM run correct on one shape and validate it.
4. Batch across shapes.
5. Compute TAWSS, OSI, RRT per shape and rank.
6. Visuals: shear maps, a leaderboard, a design-space plot.

**Limitations the brief states.** Wall shear predicts overgrowth in
direction, not reliably in size. Patient factors, surgery and the
graft material also matter. Rigid walls, Newtonian blood (constant
viscosity) and idealised shapes limit the result. So the claim is a
design-screening tool, not a patient prediction, and no healthcare
savings claim.

**Main risk.** An LBM code with correct curved walls and a pulsing
inlet is the classic way to lose a weekend. If neither engineer has
written one, choose something simpler.

**Follow-up note** (later the same night):

- The SimVascular Vascular Model Repository is real but has no
  dialysis access models. That is fine: a design map needs idealised
  shapes with controlled parameters, built in code.
- Flow data is strong: measured access flow 1186 ± 588 ml/min, graft
  diameter 6 mm, so Reynolds number (a measure of how turbulent flow
  is) about 1,200 at the mean and about 1,800 one standard deviation
  up. The top of the real range is transitional.
- Access flow is continuous, not stop-start, so the inlet waveform is
  gentle. If no published inflow waveform turns up, use mean flow plus
  one sine harmonic at 1.2 Hz and test sensitivity.
- Validate first against exact solutions: steady pipe flow
  (Poiseuille), then pulsing pipe flow (Womersley).
- Blood: density about 1050 kg/m³, viscosity 3.5 cP.
- The deciding check: confirm the chosen LBM library runs a 3-D case
  on the event hardware.

## Verification

Each line gives the claim, the verdict, what to use instead, and the
source. (A list, because a four-column table breaks the repo's
70-character table-row limit.) Verdicts: confirmed; corrected (use the replacement); secondary only
(found only in a weak source); unsupported (could not be found or
sources disagree); not found.

### Clinical

- **1-yr patency 49% AVG, 62% fistula**: secondary only. Only in a patent; cite USRDS or KDOQI. Source: [patent][p1].
- **30-70% of fistulae fail primarily**: corrected. 20-60% fail to mature; pooled about 23%. Source: [KDOQI 2019][kdoqi].
- **Medicare $2.8B on access in 2013, ~12%**: confirmed. Paper estimate, 13 years old. Source: [AJKD 2018][ajkd].
- **Medicare dialysis $48.9B in 2022, ~7%**: unsupported. ESRD total $55.3B in 2023 (snippet). Source: [USRDS 2025][usrds].
- **Dialysis 3 to 5 times a week**: corrected. Typically three times a week in centre. Source: [KDOQI 2019][kdoqi].
- **AVGs fail by venous-join narrowing**: confirmed. ~80% of failures: thrombosis on that. Source: [KDOQI 2019][kdoqi].
- **Low or oscillatory shear causes overgrowth**: secondary only. Say hypothesised; evidence is mixed. Source: [review][pmc81].

### Prior work

- **1997 JVS: optimised shape halves gradients**: confirmed. Arterial bypass, itself an optimisation. Source: [Lei 1997][lei].
- **2025 helical study: 27 models**: confirmed. Transient run on only the best 4. Source: [Benitez 2025][ben].
- **Nobody has searched the space widely**: corrected. Prior work used ~100 runs (Quicken: 103). Source: [Quicken 2021][quick].
- **No LBM or GPU work on AV access**: corrected. LBM exists (HemeLB, CPU); no GPU sweep. Source: [McCullough][mcc].
- **Typical flows and Reynolds numbers**: corrected. 700-2000 ml/min, Re about 900-1800. Source: [Loth 2008][loth].
- **Venous-join flow is turbulent**: unsupported. At most weakly transitional above ~1000. Source: [Loth 2008][loth].
- **Published mesh, step, cycle counts**: confirmed. 0.2-11M cells, 2-3 cycles, 77 h per run. Source: [Quicken 2021][quick].
- **Flexible walls change flow materially**: unsupported. Rigid is standard, ~20% off in fistulae. Source: [Bai 2019][bai].
- **Newtonian blood is fine at these shears**: unsupported. Sources split; matters in low-shear zones. Source: [Akherat][akh].
- **Fixed TAWSS, OSI, RRT danger thresholds**: corrected. No consensus; show rank stability. Source: [Malek 1999][malek].

### Tooling

- **XLB backends: JAX and Warp**: corrected. JAX, Warp and Neon; D3Q19 and D3Q27. Source: [XLB][xlb].
- **XLB curved-wall bounce-back**: confirmed. Lives inside HybridBC, untested here. Source: [XLB][xlb].
- **XLB time-varying inlet**: confirmed. Only for HybridBC; test Womersley day 1. Source: [XLB code][xlbbc].
- **XLB stable at Re 1000-2500**: corrected. BGK, KBC and LES only; no MRT shipped. Source: [XLB][xlb].
- **XLB batches shapes with vmap**: not found. Loop or one process per shape. Source: [XLB paper][xlbp].
- **XLB speed per GPU**: secondary only. Read Fig. 9 or run the benchmark. Source: [XLB paper][xlbp].
- **XLB licence**: confirmed. Apache 2.0; read LICENSE file. Source: [XLB][xlb].
- **lettuce (PyTorch LBM)**: corrected. lettucecfd/lettuce, MIT, plain walls only. Source: [lettuce][let].
- **Palabos GPU support**: secondary only. GPU version is a pre-release. Source: [Palabos][pal].
- **waLBerla GPU support**: confirmed. GPLv3; code generation, steep to set up. Source: [waLBerla][wal].
- **FluidX3D speed (D3Q19)**: confirmed. H100: 17,602 MLUPs/s FP32 (empty box). Source: [FluidX3D][fx].
- **FluidX3D memory per cell**: confirmed. 93 B FP32, 55 B FP16. Source: [FluidX3D][fx].
- **FluidX3D licence**: confirmed. No commercial or military use. Source: [licence][fxl].
- **FluidX3D pulsing inlet, wall shear**: not found. Needs custom C++. Source: [docs][fxd].
- **Blood-flow LBM codes with GPU**: confirmed. HemePure-GPU; simple walls only. Source: [HemePure][hp].
- **Warp, Taichi, PhysicsNeMo LBM**: not found. XLB's Warp backend is the Warp route. Source: [XLB][xlb].
- **Vascular Model Repository has dialysis**: confirmed. Exists; zero dialysis models in 316. Source: [VMR CSV][vmr].
- **LBM is bandwidth-bound**: confirmed. 2.37 flop per byte in FluidX3D FP32. Source: [FluidX3D][fx].
- **~19 reads and 19 writes per point**: confirmed. 304 B per update in double precision. Source: [Wellein][wellein].
- **~100 flops per point per step**: corrected. 200-400 flops. Source: [Latt 2023][latt].
- **~1 flop per byte**: corrected. 0.6-0.8 double; 2.4 FluidX3D FP32. Source: [FluidX3D][fx].
- **Fuse steps, SoA layout, push or pull**: confirmed. Fusion halves traffic; in-place helps. Source: [Wittmann][wit].
- **How LBM computes wall shear**: confirmed. From non-equilibrium populations. Source: [Matyka][mat].
- **Staircase against curved walls**: secondary only. Curved walls 2nd order, staircase 1st. Source: [Nash][nash].
- **Validate with Womersley flow**: confirmed. Use a tilted pipe to expose staircase. Source: [Nash][nash].
- **3M points, 225k steps, 1k-10k shapes**: corrected. See sizing below. Source: [FluidX3D][fx].

[p1]: https://patents.google.com/patent/US9023377B2/en
[kdoqi]: https://www.kidney.org/sites/default/files/2026-07/2019-kdoqi-guideline-vascular-access.pdf
[ajkd]: https://pubmed.ncbi.nlm.nih.gov/29602630/
[usrds]: https://usrds-adr.niddk.nih.gov/2025/end-stage-renal-disease/9-healthcare-expenditures-for-persons-with-esrd
[pmc81]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8108319/
[lei]: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:9129618&format=json&resultType=core
[ben]: https://mdpi-res.com/d_attachment/applsci/applsci-15-11064/article_deploy/applsci-15-11064.pdf
[quick]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7900962
[mcc]: https://arxiv.org/abs/2012.04639
[loth]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12577737/
[bai]: https://pubs.aip.org/aip/pof/article/31/9/091902/
[akh]: https://doi.org/10.1115/1.4035915
[malek]: https://doi.org/10.1001/jama.282.21.2035
[xlb]: https://github.com/Autodesk/XLB
[xlbbc]: https://raw.githubusercontent.com/Autodesk/XLB/main/xlb/operator/boundary_condition/bc_hybrid.py
[xlbp]: https://arxiv.org/abs/2311.16080
[let]: https://github.com/lettucecfd/lettuce
[pal]: https://arxiv.org/abs/2506.09242
[wal]: https://www.walberla.net/
[fx]: https://github.com/ProjectPhysX/FluidX3D
[fxl]: https://raw.githubusercontent.com/ProjectPhysX/FluidX3D/master/LICENSE.md
[fxd]: https://github.com/ProjectPhysX/FluidX3D/blob/master/DOCUMENTATION.md
[hp]: https://github.com/UCL-CCS/HemePure-GPU
[vmr]: https://www.vascularmodel.com/dataset/dataset-svprojects.csv
[wellein]: https://arxiv.org/pdf/1711.11468
[latt]: https://arxiv.org/pdf/2312.14742
[wit]: https://arxiv.org/pdf/1111.0922
[mat]: https://ar5iv.labs.arxiv.org/html/1203.3078
[nash]: https://arxiv.org/abs/1211.0205

## Closest prior work

- **Quicken, Delhaas, Mees, Huberts 2021** (Int J Numer Method Biomed
  Eng): dialysis graft design by global optimisation; 103 successful
  CFD runs, surrogate models, 77 hours per run. The closest match and
  the cost a GPU sweep must beat.
- **Grechy et al. 2017** (Physics of Fluids): optimisation to suppress
  unsteady flow in fistulae; calls itself the first numerical
  optimisation to design a device, so "first" claims are taken.
- **Lei, Archie, Kleinstreuer 1997** (J Vasc Surg): optimised join
  shape halves wall-shear gradients, but for an arterial bypass, not
  a dialysis graft.
- **Benitez et al. 2025** (Applied Sciences): 27 helical graft models,
  student CFD licence, full metrics on only 4. Weak competition.
- **McCullough and Coveney** (arXiv 2012.04639): HemeLB lattice
  Boltzmann in one patient's fistula on a CPU supercomputer.
- **Bai and Zhu 2019, 2021** (Physics of Fluids): LBM with flexible
  walls at a graft join; small parameter studies.
- **Liu et al. 2022** (IEEE TBME): 2,000 simulations per patient for
  Fontan heart-surgery graft design, so thousands of graft shapes is
  new only for dialysis access.

Safe pitch line: prior dialysis-graft optimisation used about 100 CFD
runs at 77 hours each; we aim for 1,000 to 10,000 at far lower cost
per run. "Nobody has used GPU LBM to sweep thousands of graft shapes"
was not contradicted; "nobody has used LBM for grafts" is wrong.

Also found: no trial shows a shape-modified graft clearly beating
standard ePTFE (cuffed and helical grafts give mixed results), so
frame the sweep as hypothesis generation, not a clinical claim.

## Tooling findings

- **XLB** (JAX, Warp, Neon; Apache 2.0; active) is the only route
  that combines curved-wall accuracy (inside HybridBC) with GPU speed.
  Untested here; no shape batching, so loop over shapes.
- **FluidX3D** is the fastest, but non-commercial licence, C++ setup
  per case, staircase walls, and no pulsing inlet or wall-shear
  output.
- **lettuce**, **HemePure-GPU**: plain bounce-back walls only in the
  fast path.
- **Palabos** GPU is a pre-release; **waLBerla** is mature but steep.
- No dialysis models in the Vascular Model Repository; build the
  shapes in code.

## Compute sizing

From the FluidX3D benchmark table (empty box, so an optimistic
floor). One run is 3 million grid points times 225,000 steps.

| GPU and precision | Per shape | 1,000 shapes | 10,000 shapes |
| --- | --- | --- | --- |
| H100 SXM5, FP32 | 38 s | 10.7 h | 106.5 h |
| H100 SXM5, FP16 storage | 23 s | 6.3 h | 63.4 h |
| A100 SXM4, FP32 | 66 s | 18.3 h | 183 h |

- 1,000 shapes fit in 28 hours on one H100 with room to spare.
- 10,000 in 28 hours needs about 4 H100s at FP32 or 2-3 at FP16.
- Each run needs only 165-279 MB, but running many at once on one GPU
  adds no speed, because the kernel is bandwidth-bound.
- Inlets, curved walls and wall-shear accumulation will slow it; a
  2-3x derate is a guess, not sourced. XLB and lettuce are likely
  slower than FluidX3D.
- The team call estimated 900 GPU hours, against about 130 GB of GPU
  memory available plus sponsor credits.
