# Computation findings: NIR light-in-tissue tools (neonatal NIRS)

Source type: PAGE = fetched page read by a small summariser model (quotes are its output, not re-checked); SNIPPET = search-result summary only; FILE = PDF I downloaded and read locally.

## 1. Tools

- MCX (CUDA, voxel Monte Carlo). GPLv3. PAGE <https://github.com/fangq/mcx> : "GPU-accelerated Monte Carlo simulator of light transport in 3D turbid media"; "NVIDIA GPUs via CUDA and AMD GPUs via HIP/ROCm". Apple Silicon: not supported ("use MCX-CL"). Speed: "hundreds to thousands of times faster than a single-threaded CPU code" (no hardware named). Photons/ms figure: not found. Validation: "validated against analytical solutions and measurements in many publications"; 141 built-in tests against golden values.
- MCX-CL (OpenCL). GPLv3. PAGE <https://github.com/fangq/mcxcl> : "NVIDIA, AMD and Intel GPUs, integrated graphics, Apple silicon, and multi-core CPUs". PMCXCL wheels "macOS (arm64 and x86_64)". Caveat quoted: on Apple silicon GPUs "about one in 20 to 60 runs may return an empty result". Speed guidance only: dedicated GPUs "20-60x faster than a multi-core CPU", integrated "3-4x"; no photons/ms on Apple hardware found (page points to mcx.space/computebench, not read).
- pmcx (Python, CUDA) PAGE <https://pypi.org/project/pmcx/> : GPLv3+, "Binary wheels with the CUDA simulator are available for Linux (x86_64) and Windows"; on macOS use pmcxcl. Returns `res['detp']`; `pmcx.meanpath()` gives mean partial path lengths.
- MMC (tetrahedral mesh Monte Carlo). GPLv3. PAGE <https://github.com/fangq/mmc> : backends "SSE/OpenMP, OpenCL, CUDA and OptiX"; Apple Silicon: CPU only per changelog ("mmclab and pmmc run on the CPU of Apple Silicon (arm64) Macs again"). Validation: checked against semi-infinite diffusion solution, "within 2% in amplitude"; 68 golden tests. Replay supported on sse/opencl/cuda, not optix. GPU speed vs CPU: not found.
- MCML (CPU, C, layered). FILE Mcman.pdf (<https://www.its.caltech.edu/~coil/mcr5/Mcman.pdf>). Licence: not found. No GPU.
- NIRFAST / NIRFASTer / NIRFASTerFF (diffusion FEM, Python successor NIRFASTerFF). SNIPPET: NIRFASTerFF gives "a performance boost of 25-45% on GPU and up to 20% on CPU" over NIRFASTer; GPU FEM forward "10-fold speed increase" (Doulgerakis 2017, adult head). Licence, Apple Silicon: not found (PMC page blocked by captcha). Paper: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12587457/>
- Toast++ (diffusion FEM, C++ with Matlab/Python bindings). SNIPPET: GPLv3 (SourceForge <https://sourceforge.net/projects/toastpp/>). GPU, Apple Silicon, speed: not found.
- New: arXiv 2511.22779 (Yan, Dwyer, Kaeli, Fang), "Accelerating mesh-based Monte Carlo simulations using contemporary graphics ray-tracing hardware"; reference list mentions Metal ray tracing. Results not read (PDF unreadable to the summariser; saved binary only).

## 2. Reuse of one Monte Carlo run

- MCX-CL PAGE: detected photons carry per-medium partial path; "Save detected-photon seeds with -q 1, then replay them with -E file_detp.jdt and an output type such as -O J" (Jacobians). Perturbation Monte Carlo from saved detected-photon data works "without rerunning the simulation". Caveat from page: volumes with per-voxel properties carry no per-medium partial path data (so layered/labelled-medium head models are needed for partial paths).
- White / scaling Monte Carlo (SNIPPET, search summary): one run, absorption applied afterwards by microscopic Beer-Lambert. "In the case of scaling of the absorption coefficient, the convergence is always rigorous both for the forward and inverse problems"; scattering scaling needs "rescaling ... individually for each photon biography" and the regenerated result "inherits the very same noise". Partial pathlengths must be stored per detected photon, per layer (storage cost). Key refs named in snippet: Graaff 1993; Alerstam, Andersson-Engels, Svensson 2008 J Biomed Opt; Liu and Ramanujam 2007 JOSA A (multilayer scaling), <https://lightningspectroscopy.xmu.edu.cn/article/Liu-2007-JOSAA-ScalingMC.pdf> ; GPU rescaling paper PMC3829559 (2013, 10M-photon run). Speed-up factors: not found (not read).
- Preserved exactly: absorption changes (Beer-Lambert on stored paths, within the same geometry, with fixed scattering). Not preserved without per-photon rescaling: scattering changes. Geometry changes: need new run.

## 3. Array-framework photon Monte Carlo and validation numbers

- Tissue photon Monte Carlo in JAX/PyTorch: not found in my searches (SNIPPET). Nearest: LUCiD (NeurIPS ML4PS 2025), JAX differentiable photon detection for particle detectors, "one million photons with gradients takes 30ms on a single GPU" (SNIPPET, <https://ml4physicalsciences.github.io/2025/files/NeurIPS_ML4PS_2025_330.pdf>); ray-trax (JAX, gas, not tissue). Gap, so a JAX/PyTorch tissue code would be novel, but discrete scattering breaks naive autodiff.
- MCML reference values, FILE Mcman.pdf section 6.1:
  - Slab, matched boundary, n=1, mua=10/cm, mus=90/cm, g=0.75, d=0.02 cm, 10 runs of 50,000 photons: van de Hulst Rd 0.09739, Tt 0.66096; mcml Rd 0.09734 (se 0.00035), Tt 0.66096 (se 0.00020); Prahl 1989 Rd 0.09711, Tt 0.66159.
  - Semi-infinite, mismatched n=1.5, mua=10, mus=90, g=0, 10 runs of 5,000 photons: Giovanelli 1955 Rd 0.2600; mcml 0.25907 (se 0.00170); Prahl 1989 0.26079 (se 0.00079).
  - The manual also has angularly resolved tests (section 6.2), not extracted.

## 4. ML surrogates

- Lan, McClarren, Vishwanath, Biomed Opt Express 2023 (SNIPPET): neural network forward model trained on Monte Carlo, used to build the lookup table; "accuracy comparable" to the Monte Carlo inverse, faster; tested on liquid phantoms. <https://www.cas.miamioh.edu/~vishwak/resources/pubs/2023-BOE-QingLan_etal-Neural%20network-based%20inverse%20model.pdf>
- Nguyen et al., J Biomed Opt 2021 (SNIPPET): deep learning vs random forest, gradient boosting, GLM vs Monte Carlo lookup table on six-wavelength reflectance; "deep learning model had much faster runtimes". <https://pmc.ncbi.nlm.nih.gov/articles/PMC7969972/> Numbers not read.
- Neonatal-specific NN inverse model for NIRS oximetry: not found. Neonatal head Monte Carlo meshes (29 and 44 weeks postmenstrual age) fitted with photon diffusion: <https://re.public.polimi.it/bitstream/11311/1175668/4/iris_boe-12-4-1905.pdf> (SNIPPET). Synthetic-data fNIRS ML: <https://arxiv.org/pdf/2405.11242> (title only).

## 5. Cost scaling

Not extracted from the papers' own statements (no paper text read for this). Only supported statements: replay computes Jacobians from saved seeds of detected photons only (MCX-CL page); white MC needs one run for all absorption values (snippet); Monte Carlo lookup-table fitting is "a time-consuming iterative process" (snippet, Nguyen 2021). Per-source-detector-pair counts: not found.

## Blockers

Search was thin (one pass); PMC and arXiv PDFs defeated the summariser. Photons/ms numbers, NIRFASTerFF licence, white-MC speed-ups and cost-scaling statements need a second pass with pdftotext on the downloaded papers.
