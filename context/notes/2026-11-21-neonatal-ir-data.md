# Neonatal IR monitoring: data, models, prior work

Source tags: [page] = fetched page text; [snip] = search snippet only. Several PMC pages blocked (browser check), so those items are snippet-level or not found.

## 1 Head models

- UCL/Collins-Jones database, 215 individual models, 29-44 wk PMA, from dHCP [page] <https://pmc.ncbi.nlm.nih.gov/articles/PMC7814762> : "at ages 29-44 weeks postmenstrual age". Voxel mask 0.5 mm isotropic plus tetrahedral mesh, scalp surface, 10-5 positions; 9 labels (extra-cerebral scalp+skull combined, outer CSF, cortical GM, WM, ventricles, cerebellum, deep GM, brainstem, hippocampus). Scalp and skull NOT separated in this database.
- Licence of database: not found (paper is CC BY 4.0). Download: "freely available at <https://www.ucl.ac.uk/dot-hub>"; data statement says release "following an embargo". Sign-up: not found. Optical values not supplied; user assigns them.
- Older Brigadoi 4-D model, weekly 29-44 wk, layered mask (extracerebral, CSF, GM, WM) [snip] <https://research.unipd.it/retrieve/e14fb26d-cd63-3de1-e053-1705fe0ac030/> ; hosted <https://www.ucl.ac.uk/medphys/research/4dneonatalmodel> (not opened).
- Atlas effects paper uses 165 atlas models, MC + FEM [snip] <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10460200/>
- dHCP raw data: developingconnectome.org (access terms not checked).

## 2 Optical properties

- Scalp 0.018 /mm absorption, 1.9 /mm reduced scattering, from Dehaes 2013 [page, via PMC7814762] ("absorption coefficient and reduced scattering coefficients of 0.018 and 1.9 mm-1 for scalp"). Brain values in that paper: not found.
- Standard sources named by search, values not read: Zhao 2005 in vivo infant/neonate brain (J Biomed Opt 10(2) 024028) <https://www.spiedigitallibrary.org/journals/Journal-of-Biomedical-Optics/volume-10/issue-2/024028/> ; Spinelli 2017 TD-NIRS neonate brain (Neurophotonics 4(4) 041414) ; Dehaes 2011 HBM; Fukui (not found). Both [snip].
- Melanin/skin tone: no neonatal tissue-layer values found. Phantom: "up to 15%" change with melanin (Afshari, Biomed Opt Express 2022) [snip] <https://pmc.ncbi.nlm.nih.gov/articles/PMC9830604> ; MC review of pigmentation, Sensors 2026 <https://openaccess.city.ac.uk/id/eprint/37902/1/sensors-26-02337-v2.pdf> [snip].

## 3 Datasets

- PhysioNet Preterm Infant Cardio-Respiratory Signals: 10 preterm infants, ECG 500 Hz, resp 50 Hz, 1.6 GB, ODC-By 1.0, open, no NIRS/PPG [page] <https://physionet.org/content/picsdb/> : "Total uncompressed size: 1.6 GB."
- MIMIC-III Waveform DB: adult+neonatal ICU, PPG/ECG/SpO2, ~3 million hours; PPG at 125 Hz; credentialing for clinical part; neonatal filtering needed [snip] <https://www.physionet.org/content/mimic3wdb/1.0/> (waveform vs credentialing boundary unverified).
- Preterm cerebral+splanchnic NIRS during transfusion, 29 infants, FORE-SIGHT, Data in Brief 2022 DOI 10.1016/j.dib.2022.108824 <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9803924/> [snip]; repository/licence not found.
- Infant fNIRS, 104 healthy 4-month-olds, Sci Data 2022 <https://link.springer.com/10.1038/s41597-022-01210-y> [snip]; not neonatal ICU. openfnirs: not searched.
- No public neonatal PPG/NIRS ICU set with ground-truth StO2 found.

## 4 Prior simulation studies

- Amendola et al.: realistic meshes at 29 and 44 wk PMA, scalp/skull/CSF/brain, TD-NIRS; thinner extracerebral tissue -> stronger CSF influence, tHb underestimated more in younger; saturation accuracy good [snip] <https://re.public.polimi.it/bitstream/11311/1175668/4/iris_boe-12-4-1905.pdf> (config count not found).
- Ostojic 2020 skull thickness in silico (Adv Exp Med Biol 1232:33-38): "<=6 mm" superficial layer keeps StO2 accurate [snip], single catalogue summary, verify <https://link.springer.com/doi/10.1007/978-3-030-34461-0_5>
- Pichler-type clinical FD-NIRS: skin/bone/CSF thickness "do not seem to affect" cerebral oxygenation significantly [snip] <https://www.spiedigitallibrary.org/journals/Journal-of-Biomedical-Optics/volume-19/issue-1/017004/> ; noted thickness data lacking for preterms.
- 30 mm spacing: partial pathlength depends on inner skull depth, sensitivity on CSF thickness [snip]. Short-channel optimum, Neurophotonics 2(2) 025005 [snip].
- Algorithms on neonatal mesh: median StO2 error 0.4% BRUNO, 4.2% BF, 9.5% SRS [snip] <https://pmc.ncbi.nlm.nih.gov/articles/PMC7901317> (check).
- Dehaes: curvature dominant error in neonates; fontanel correction factors [snip].
- Open/unfound: hair, gestational-age-specific effects, skin tone in neonatal MC, commercial device algorithms. Evidence of gaps = absence in my searches, not a stated claim by a paper.

## 5 Large sweeps / AI

- No neonatal thousands-of-configuration MCX sweep, and no LLM-hypothesis system for tissue optics, found.
- Nearest: fetal SpO2 ML trained on large MCX simulated set, 90% errors <7.5% [snip]; fNIRS synthetic data with parametric heads arXiv 2405.11242, arXiv 2605.30552 (mesh MC full-head simulator) [snip]; GRACE agentic MC for high-energy physics arXiv 2602.15039 [snip]. Not neonatal.
