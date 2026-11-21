# Neonatal IR monitoring: clinical and field picture

**Warning:** a verification pass found two claims in this note wrong, and one unverified.

- The SafeBoosC II figures are cited to a page that is a different paper.
- The "2.4-fold" pulse-oximetry figure for preterm infants has no valid source: the cited page is a study of children.
- The oximeter disagreement figures (3.5% bias, 11.8% limits of agreement) could not be verified.

PROVENANCE: WebFetch was blocked on pubmed and PMC (cookie/browser check page), so EVERY fact below comes from a search-result snippet, not the page itself. Quotes are the snippet text. Verify before citing.

## 2. Proven / unproven

- SafeBoosC-III, NEJM 2023 (snippet from <https://www.pubmed.gov/37075142/>): infants <28 wk GA, within 6 h of birth, oximetry-guided vs usual care for 72 h. "272 of 772 infants (35.2%) in the cerebral oximetry group, as compared with 274 of 807 infants (34.0%) in the usual-care group". Primary outcome: death or severe brain injury at 36 wk PMA. RR 1.03 (CI cut off in snippet: not found). Null.
- SafeBoosC-III 2-year follow-up, JAMA Pediatrics 2026 (<https://pubmed.ncbi.nlm.nih.gov/42008246/>): "292 of 620 infants (47.1%) ... compared with 321 of 669 infants (48.0%)", RR 0.96, 97.5% CI 0.85-1.07, P = .45; Bayley cognitive similar. Null.
- SafeBoosC II, BMJ 2015;350:g7635 (<https://pmc.ncbi.nlm.nih.gov/articles/PMC4841944>, snippet): 166 infants, 8 NICUs; primary outcome burden of hypo/hyperoxia (time outside rStO2 55-85%); "reduced the median burden of hypo- and hyperoxia by 58% (95% CI 35-73%)". Feasibility/physiology only, not outcomes. Its 2-year follow-up (Acta Paediatrica) found no neurodevelopmental benefit (snippet).
- Review position, ESPR NIRS group, Pediatric Research 2024 (<https://www.nature.com/articles/s41390-024-03137-z.pdf>, snippet): "NIRS-guided treatment in extremely preterm infants during transitional circulation does not improve clinical outcomes." Formal society guideline on routine cerebral NIRS: not found.
- Vesoulis 2024 narrative review: value is "detection of cerebral hypoxia, even when other monitors do not show signs of clinical deterioration" (snippet; no URL captured).

## 1. Methods (what each measures), from snippets

- Cerebral NIRS: tissue oxygen saturation (StO2/rStO2). Commercial: INVOS, FORE-SIGHT, NIRO, SenSmart, OxyPrem; Masimo O3 got FDA 510(k) for expanded indications incl. neonatal, Aug 2025 (<https://www.massdevice.com/masimo-wins-fda-clearance-for-neonatal-o3-regional-oximetry-indication/>).
- fNIRS / wearable HD-DOT: brain activation maps. Uchitel et al., NeuroImage 2023: "first cot-side study of newborn infants using wearable HD-DOT in a clinical setting" (<https://doaj.org/article/48c3fc7e5147420eb9ebcb570f8856bc>). Flexible lightweight system, Neurophotonics 2021 (<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7995199/>).
- Broadband NIRS: oxidation state of cytochrome c oxidase (mitochondrial metabolism). DCS: blood flow index, "relative changes track well with gold-standard blood flow measures". Combined B-NIRS+DCS device (<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6154190/>); NNeMo portable device in post-haemorrhagic ventricular dilatation (<https://pmc.ncbi.nlm.nih.gov/articles/PMC7407524>).
- Camera / thermography: 2024 Frontiers Pediatrics review (<https://frontiersin.org/journals/pediatrics/articles/10.3389/fped.2024.1442753/full>): "integration ... into standard NICU clinical practice remains limited". Preterm camera study 2019: HR mean absolute error 2.3 bpm (<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6908711/>); Cambridge NICU RGB-D 2025: HR error 7.69 bpm, RR 4.83/min (<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12081704/>).
- Pulse oximetry: SpO2 (see bias below). Transcutaneous bilirubin and non-invasive glucose: not found (search did not cover them).

## 3. Measurement problems

- Device disagreement, newborns: INVOS 5100C vs FORE-SIGHT, bias "up to 3.5%", "limits of agreement reached 11.8%" (<https://clinicaltrials.gov/study/NCT01665287> listed; paper not opened). 12 term infants: steady-state means 78.4% INVOS vs 86.2% FORE-SIGHT, proportional bias. INVOS vs NIRO "mean differences of 10%" in some reports.
- Phantoms: oximeter-specific offsets; "guidelines built on one oximeter's readings cannot be applied directly to other oximeters"; disagreement also depends on phantom haemoglobin (<https://pmc.ncbi.nlm.nih.gov/articles/PMC4986807>, <https://doi.org/10.1038/pr.2013.133>).
- Pigmentation, NIRS: Afshari et al., Biomed Opt Express 2022 phantom (<https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9830604/>): saturation drops with simulated melanin, "up to 15%", "strongest in a neonatal sensor". Quaresima, Crit Care 2023 commentary (<https://link.springer.com/doi/10.1186/s13054-022-04295-4>). Children INVOS clinical: darker skin lower values (<https://pmc.ncbi.nlm.nih.gov/articles/PMC12520187>). No neonatal clinical skin-tone NIRS study found.
- Pigmentation, pulse ox, neonates: retrospective preterm <32 wk, overestimation "2.4-fold greater for Black infants" (<https://pmc.ncbi.nlm.nih.gov/articles/12087261/> snippet, link uncertain); NeoPODS prospective reports no significant difference, but company-linked summary only; NCT05994417 (<https://clinicaltrials.gov/study/NCT05994417>) no results found. Mixed.
- Scalp/skull/CSF: Monte Carlo 29 and 44 wk PMA meshes with extracerebral, CSF, brain domains (<https://pmc.ncbi.nlm.nih.gov/articles/PMC6869951> area); 4D atlas 29-44 wk PMA (Brigadoi, research.unipd.it); fontanel changes recovery accuracy (snippet); StO2 error on a neonatal mesh 0.4% BRUNO, 4.2% BF, 9.5% SRS (snippet). No study found quantifying contamination vs gestational age directly.

## 4. Growth signals 2024-2026

- FDA draft guidance, pulse oximeters, 7 Jan 2025 (<https://www.federalregister.gov/> ; <https://www.govinfo.gov/content/pkg/FR-2025-01-07/html/2024-31540.htm>): skin-tone testing, Monk scale, labelling. Final version: not found.
- Masimo O3 neonatal clearance Aug 2025 (above).
- NIH R21HD117308, wearable NIRS neonatal blood pressure, Dec 2024-Nov 2026, $237,827 (<https://reporter.nih.gov/search/CwYipXX5EU2S_P33GsqYzw/project-details/11036200>).
- fUSiON (HD-DOT + functional ultrasound cot-side cap), Cambridge BRC, Nov 2025 (<https://cambridgebrc.nihr.ac.uk/2025/11/07/cutting-edge-baby-brain-scan-technology-is-world-first/>): "world first" is the institution's claim.
- Wearable fiber-free DSCFO preprint, piglets and preterm infants (snippet).
- Wearable-neonatal-NIRS company with FDA clearance: not found.

## 5. Open questions named by reviews (snippets)

- Does NIRS-guided care improve outcomes beyond physiology (ESPR 2024)? Training and standardised interpretation needed. Interpretation in clinical context. Delivery-room use and low-resource settings (Cureus 2025 review, <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12500479/>).
- Cross-device comparability and absolute thresholds; pigmentation robustness; DCS/B-NIRS translation to routine use.

## Implication for a hackathon (my reading, not from sources)

Gaps with sourced support: device disagreement, melanin and neonatal sensor bias, layer contamination vs age. All are forward-simulation or inverse-problem questions (Monte Carlo photon transport is embarrassingly parallel).
