# EEG as a use case: checked evidence (Sat 21 Nov)

The facts below were collected by one agent and each source was re-opened by a second, on 21 Nov 2026, in one pass. Where the second check found a claim only partly right, the corrected version is written here, not the original wording.

## EEG devices today and where the answer is computed

- NeuroPace RNS-320 has an estimated battery life of about 10.8 years at medium settings. It is FDA approved for adults 18 and over with drug-resistant focal epilepsy. It responds to detected activity with pulses (a closed-loop implant). The page does not say where detection runs. Source: https://www.neuropace.com/patients/rns-system/
- Ceribell Infant Seizure Detection Software (FDA K252070, Nov 2025) marks previously acquired EEG sections in neonates of 25 to 44 weeks postmenstrual age and in infants under 1 year. It is an aid to clinicians. The marking is retrospective and is not a standalone diagnosis. Source: https://www.accessdata.fda.gov/cdrh_docs/pdf25/K252070.pdf
- Ceribell reports 95% sensitivity, 97% specificity and 99.9% NPV for status epilepticus detection. These are company-reported figures from a conference poster, for status epilepticus only. They are not peer-reviewed and not device-level performance. The page does not say whether the algorithm runs on the device or in the cloud. Source: https://ceribell.com/
- Epitel REMI-AI Discrete Detection Module (FDA K231779) analyses previously acquired 4-channel scalp EEG. It does not mark in real time and gives no diagnostic conclusion. Source: https://www.accessdata.fda.gov/cdrh_docs/pdf23/K231779.pdf
- REMI is validated against standard-of-care 19-channel full-montage video-EEG, while it uses its own 4 channels. Source: https://www.accessdata.fda.gov/cdrh_docs/pdf23/K231779.pdf
- UNEEG SubQ is described as a subcutaneous EEG measuring device with three electrodes. Its recorder retrieves and transfers raw EEG data and self-reported seizures to the hospital. The Analyzer is an AI software platform that analyses the recording in minutes and flags suspected seizure activity for review. The page never states where the Analyzer runs, and the word cloud does not appear on it. That the decision is not made on the implant is a reasonable inference, but it is not stated. Source: https://www.uneeg.com/en/
- Medtronic Percept PC records at 250 Hz in clinic. Battery life gets shorter when BrainSense sensing is used. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC11299490
- Percept PC at home stores 10-minute averages of power in a 5 Hz band instead of raw samples. This is data reduction on the device. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC11299490
- The Dreem 3S headband has 6 electrodes and an accelerometer. Beacon Biosignals announced its FDA 510(k) clearance for automated sleep staging in a press release on 13 Sept 2023. That is the announcement date. The FDA decision date in openFDA record K223539 is 18 Aug 2023. Beacon now sells the device as Waveband (June 2025). The article does not say where processing runs. Source: https://aasm.org/fda-clears-ai-assisted-sleep-monitoring-device-dreem-3s/
- A Cochrane review of 16 studies with 562 newborns found that amplitude-integrated EEG (aEEG) may not be accurate enough for diagnosing neonatal seizures. Source: https://www.cochrane.org/evidence/CD013546_how-accurate-simplified-and-easily-available-electroencephalography-called-amplitude-integrated-eeg
- For an implantable brain-machine interface wireless unit estimated at under 50 mW, signal processing, data converters and other modules take 80 to 90% of the power budget and the radio takes the rest. This is a design estimate, not a measurement, for a chest-wall unit. Source: https://par.nsf.gov/servlets/purl/10109387
- Common guidelines for chronic heat from brain implants use limits of 2 C temperature change and 40 mW/cm2 surface heat flux. These limits are not the paper's own mouse-brain figure. Source: https://arxiv.org/pdf/1306.5709
- In a 400-neonate NICU cohort, 24% (25 of 105) of neonates with electrographic seizures had no clinical correlate. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4696927
- In nine term neonates with perinatal arterial ischaemic stroke, 78% of seizure events were electrographic only. This rests on nine babies. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4106759

## Published EEG classifier chips

- An 8-channel system-on-chip with a patient-specific SVM seizure classifier uses 2.03 uJ per classification and reached 84.4% in a rapid eye-blink test. The source is an MIT annual report from 2012 (ISSCC, Feb 2012), not a 2013 paper. The 84.4% is an eye-blink proxy, not a seizure-detection result. Source: https://mtlsites.mit.edu/annual_reports/2012/an-8-channel-scalable-eeg-acquisition-soc-with-fully-integrated-patient-specific-seizure-classification-and-recording-processor
- A gradient-boosted-tree chip (Shoaran et al., 2018) in 65 nm uses 41.2 nJ per classification. It was tested on iEEG of 26 patients with F1 of about 88% block-wise. The tree count is set per patient. Source: https://authors.library.caltech.edu/92186
- The NeuralTree SoC (65 nm) uses 0.227 uJ per classification. Sensitivity is 95.6% on an EEG dataset and 94% on an iEEG dataset. It uses patient- and disease-specific biomarkers. Source: https://arxiv.org/abs/2205.06090
- SOUL is an unsupervised online-learning seizure classifier in TSMC 28 nm. It takes 0.1 mm2 and 1.5 nJ per classification. Sensitivity is 97.5% on CHB-MIT and 97.9% on NeuroVista iEEG, at over 95% specificity. Source: https://arxiv.org/abs/2110.02169
- An edge deep-learning study on CHB-MIT (processor level, not custom gates) reports an LSTM with 97.61% sensitivity at 0.071 false positives per hour. Source: https://arxiv.org/abs/2012.00307
- MUXnet is a closed-loop SoC with a table-lookup, multiplier-free neural network for on-chip sleep staging. It uses 0.2 uJ per class and reaches 82.4% accuracy. Source: https://arxiv.org/abs/2401.03396
- A logic gate network, or lookup-table network (LGN/LUTN), exists for ECG arrhythmia. On MIT-BIH, 4 classes, inter-patient, it reaches up to 94.41% accuracy. The classifier part alone takes 0.46 nJ. The whole ECG system uses 8.25 uJ per inference on an FPGA. Source: https://arxiv.org/abs/2609.32854

## Open EEG datasets

| Name | People and events | Size | Licence | Access |
| --- | --- | --- | --- | --- |
| CHB-MIT Scalp EEG | 22 subjects, 198 seizures | 42.6 GB | ODC-By 1.0 | Open, no account |
| Siena Scalp EEG | 14 patients, 47 seizures, about 128 h | 20.3 GB (13.0 GB zip) | CC BY 4.0 | Open |
| Sleep-EDF Expanded | 197 whole-night recordings (153 SC, 44 ST) | 8.1 GB | ODC-By 1.0 | Open |
| Helsinki neonatal EEG | 79 term neonates, 39 with seizures | 4.3 GB | CC BY 4.0 | Open on Zenodo |
| TUH EEG Seizure Corpus (TUSZ) | 315 subjects, 822 sessions, 280 with seizures | Not checked | None stated on page | Signed form, then rsync over SSH key |
| VitalDB | 6,388 surgical cases, BIS monitor in 5,566 | Not stated | CC BY 4.0 | Provider site, its terms of use |

Details per dataset:

- CHB-MIT typically has 23 channels at 256 Hz. Uncompressed size is 42.6 GB. Source: https://physionet.org/content/chbmit/1.0.0/
- Siena records at 512 Hz. Channel count per subject is in subject_info.csv. Source: https://physionet.org/content/siena-scalp-eeg/1.0.0/
- Sleep-EDF Expanded records EEG at 100 Hz (Fpz-Cz, Pz-Oz). Source: https://physionet.org/content/sleep-edfx/1.0.0/
- Helsinki: the page gives no channel count or sample rate. Source: https://zenodo.org/records/2547147
- TUSZ access needs a signed form emailed to the maintainers, then credentials and rsync over an SSH key. Source: https://isip.piconepress.com/projects/nedc/html/tuh_eeg/
- TUSZ counts are from v1.2.0 (Dec 2017): 315 subjects, 822 sessions, 280 with seizures. The paper says the entire database has over 504 h of data. It does not word that as the v1.2.0 figure. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6246677/
- VitalDB has two EEG wave channels at 128 Hz from the BIS monitor. Source: https://vitaldb.net/dataset/

## Several outputs from one chip, and wake-up designs

- SleepViT is an ASIC design in 65 nm, 0.754 mm2, with 31.6k weights. It scores 4 sleep stages at 82.9%, trained on MASS SS3. It was designed and synthesised, not fabricated. The 0.56 mW is an effective average with aggressive power gating. Without gating it is 6.54 mW dynamic plus 11.0 mW leakage over a 45.6 ms inference window. Source: https://arxiv.org/abs/2502.16334
- The ECG logic gate network above gives 4 classes from one input, at 94.41% accuracy on MIT-BIH. Source: https://arxiv.org/abs/2609.32854
- An EPFL two-stage iEEG seizure detector on an FPGA powers its detection stage only after a monitoring stage flags something. The activation ratio is 0.272. It reached 100% sensitivity on 24 seizures in 120 h from six patients. Source: https://infoscience.epfl.ch/record/293538?ln=fr

## Looked for and not found

- Any EEG classifier built as a logic gate or lookup-table network. Searches returned only conventional FPGA neural network, SVM and QDA designs. The only gate-network paper found is for ECG.
- Any automated architecture search or LLM-agent flow that outputs EEG hardware. Only generic ASIC agents were found.
- A multi-type seizure classification chip was not searched separately.
- A five-stage sleep scoring chip. Only four-stage designs were found.
- An always-on EEG chip that wakes a larger processor, with measured silicon. Only the EPFL FPGA design was found.
- A gate or lookup-table count for a fabricated multi-class chip. Searches gave power only.
- Single-lead ECG sample rate and channel count from a primary source.
- Clinical scalp EEG sample rate from a primary quote.
- The BIS monitor 0 to 100 index range and where it is computed, from a primary source.
- Muse headband and Dreem sampling rates.
- Medtronic's own battery life number for Percept PC.
- A published share of radio power for wearable (non-implant) EEG. Only the 80 to 90% implant design estimate was found.
- Newborn aEEG monitor CE marking, other than the Ceribell FDA clearance.
- Seizure sensitivity, false alarms per hour and process node for the 2012 8-channel chip.
- Total VitalDB download size, Siena total channel count, Helsinki channels and sample rate, and current TUSZ (v2.x) counts.

## Wording to avoid

- Do not say the Dreem 3S was cleared on 13 Sept 2023. That is the press-release date. The FDA decision was 18 Aug 2023, and the device is now sold as Waveband.
- Do not say UNEEG runs its analysis in the cloud. The page never says where it runs.
- Do not present the Ceribell 95% and 97% figures as peer-reviewed or as device performance. They are company-reported, from a conference poster, for status epilepticus.
- Do not call the 80 to 90% power split a measurement. It is a preliminary design estimate for a chest-wall unit.
- Do not credit the 2 C and 40 mW/cm2 heat limits to the paper's own experiment. They are common guideline values.
- Do not generalise from the nine-neonate stroke result.
- Do not quote 0.46 nJ as the cost of the whole ECG gate network. It is the classifier part only. The whole system uses 8.25 uJ per inference on an FPGA.
- Do not cite 2000 to 2990 lookup tables for the earlier ECG version. That paper was withdrawn and its numbers changed.
- Do not call SleepViT a built chip, and do not quote 0.56 mW without saying it needs power gating (17.5 mW before gating).
- Do not describe the 84.4% from the 2012 chip as seizure accuracy. It is an eye-blink test. Do not date it 2013.
- Do not state the TUSZ 504 h figure as the v1.2.0 size.
- Say only that NeuroPace RNS-320 responds to detected activity with pulses. Do not say where detection runs.
