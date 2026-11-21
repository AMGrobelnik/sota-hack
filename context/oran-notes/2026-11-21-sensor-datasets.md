# Open datasets for second-device case studies, 21 Nov 2026

Research note. One search pass per sensor type on Sat 21 Nov; dataset contents are from
the papers' or repositories' own descriptions, and licences were not all checked on the
hosting pages. Check the licence on each page before downloading.

## Summary

| Sensor | Dataset | Contents | Licence | Fit |
|---|---|---|---|---|
| Radar | FAU clinical radar vital signs, Sci Data 2020, DOI 10.1038/s41597-020-00629-5, figshare 10.6084/m9.figshare.12186516 | 24 h of 24 GHz continuous-wave radar from patients, synchronised with ECG, impedance cardiogram and continuous blood pressure | Paper CC BY 4.0; figshare terms to check | Best second device now: open, contactless, ECG gives ground truth |
| Radar | FAU radar heart sounds, figshare 10.6084/m9.figshare.11778900 | 13,376 s, references: 3-lead ECG, electronic stethoscope, airflow sensor | Check | Good |
| Radar | FMCW radar, 50 children under 13 (PMC8036835), FigShare | Raw radar with synchronised references | "Free for academic use with credit" | Paediatric angle |
| Red/IR light (PPG) | PhysioNet pulse-transit-time-ppg v1.1.0 | 66 records, multi-site multi-wavelength PPG, plus inertial, pressure, temperature, ECG, BP and SpO2 numerics | PhysioNet open | Closest real-data match to "infrared plus another wavelength"; SpO2 reference is a periodic oximeter value, not blood gas |
| Red/IR light | OpenOximetry | Red and infrared PPG at 86 Hz; reference SpO2 averaged across oximeters | Access not checked | Good if downloadable |
| Red/IR light | Multiwavelength PPG with BP and HR, Mendeley Data gs7jvwtcgt (127 subjects) | Red and infrared PPG | Check | For blood pressure, not oxygen |
| Neonatal brain NIRS | None found with ground-truth oxygen | | | Simulate: 215 open newborn head models (UCL dot-hub) plus MCX-CL (runs on Apple silicon); see the team's neonatal IR notes |
| Thermal, neonatal | Greek neonatal sepsis thermal repo, github.com/marinocom/Early-detection-of-neonatal-sepsis-using-thermal-images | Per-baby central vs peripheral temperature time series, annotated zone dataset zip; Patras hospital and UAB collaboration | No licence on the repo, so reuse needs the authors' permission | Clinically ideal (a few temperature inputs, tiny chip); used by Oran's MIT Grand Hack project NeoTherm |
| Infant video | AIR-400 infant respiration videos (arXiv 2512.06888), code github.com/michaelwwan/air-400 | 275 new annotated videos, 10 infants (plus earlier AIR-125) | Stated public; check | Unclear whether thermal or RGB |
| Neonatal RGB-D | Cambridge repository, neonatal vital signs from RGB-D video | Ground truth vitals and processed video-derived signals | Terms not shown | Check |
| Camera vital signs (rPPG) | UBFC-rPPG (about 42 subjects), PURE (10), MMPD (660 one-minute phone videos, Fitzpatrick 3 to 6) | Face video with pulse-oximeter ground truth | Not found; usually research-only on request | Strongest privacy story (raw video never leaves the chip); MMPD covers darker skin |

## Not found in this pass

- A public neonatal thermal video dataset (thermal NICU studies exist, about 15 infants
  and 42 h of video, but their data is not shown as public).
- A red/IR dataset with arterial blood gas (SaO2) as the reference.

## Recommendation

1. Radar as the second device: open data with a synchronised ECG reference.
2. PhysioNet multi-wavelength PPG as the real-data version of the infrared idea; it fits
   the existing PhysioNet pipeline.
3. Neonatal brain oxygen by simulation only: the strongest parallelism story, bigger build.
4. NeoTherm thermal data only after written permission from the Greek authors.

## Sources

- Radar, clinical: https://pmc.ncbi.nlm.nih.gov/articles/PMC7479598
- Radar, heart sounds: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7018953/
- Radar, children: https://pmc.ncbi.nlm.nih.gov/articles/PMC8036835
- PhysioNet PPG: https://www.physionet.org/content/pulse-transit-time-ppg/1.1.0/
- Multiwavelength PPG: https://data.mendeley.com/datasets/gs7jvwtcgt/1
- Greek thermal repo: https://github.com/marinocom/Early-detection-of-neonatal-sepsis-using-thermal-images
- AIR-400: https://arxiv.org/abs/2512.06888v1
- MMPD: https://ubicomplab.cs.washington.edu/pdfs/mmpd.pdf
- rPPG-Toolbox (preprocessing for UBFC, PURE, MMPD): https://arxiv.org/pdf/2210.00716
