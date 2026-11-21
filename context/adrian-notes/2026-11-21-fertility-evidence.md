# Fertility medicine as a use case: checked evidence (Sat 21 Nov)

The facts below were collected by one agent and each source was re-opened by a second agent, on 21 Nov 2026, in one pass. Pages were read through a summarising fetch tool, so quotes come from its reading.

## Fertility sensing devices today

- Natural Cycles software has an FDA decision dated 24 Jun 2021 (K202897) for contraception or conception. The submission added the Oura ring as a temperature source. Source: https://fda.innolitics.com/device/K202897
- Apple Watch gives retrospective ovulation estimates from wrist temperature on Series 8 or later and Ultra. Apple says not to use Cycle Tracking for birth control. Source: https://support.apple.com/120357
- The Mira Ultra4 kit measures four urinary hormones (FSH, LH, E3G, PdG). Results show in the Mira App. Source: https://shop.miracare.com/pages/mira-app
- An intrauterine sensor is in an early clinical trial at Princess Anne Hospital, Southampton (GBP 850,000). It measures oxygen, pH and temperature in the womb and sends data wirelessly twice an hour. Verso Biosense is the Oxford company developing it, not the device name. The page says nothing about regulatory status, so do not imply it is approved. Source: https://research.uhs.nhs.uk/news/tiny-implantable-device-trialled-to-detect-fertility-problems

## Privacy: regulator actions and the law

- FTC, June 2021: Flo Health disclosed sensitive health data of millions of users to marketing and analytics firms including Facebook and Google. The page gives no exact user count. Source: https://www.ftc.gov/news-events/news/press-releases/2021/06/ftc-finalizes-order-flo-health-fertility-tracking-app-shared-sensitive-health-data-facebook-google
- FTC, 2023: Easy Healthcare (Premom) disclosed health data to AppsFlyer and Google. It carries a $100,000 civil penalty under the Health Breach Notification Rule and a ban on sharing health data for advertising. Call it a proposed order, as the page does. Source: https://www.ftc.gov/news-events/news/press-releases/2023/05/ovulation-tracking-app-premom-will-be-barred-sharing-health-data-advertising-under-proposed-ftc
- UK ICO review of period and fertility apps, published 8 Feb 2024: "no serious compliance issues or evidence of harms were identified in this review". No enforcement action is mentioned. The page also says developers could improve transparency and data security. Source: https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2024/02/ico-urges-all-app-developers-to-prioritise-privacy
- GDPR Recital 35 defines health data broadly as all data pertaining to the health status of a data subject. Source: https://gdpr-info.eu/recitals/no-35/
- The UK GDPR special category list on the ICO site includes data concerning health and sex life. Source: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/special-category-data/what-is-special-category-data/
- A law firm (a secondary source) says most menstrual, fertility, pregnancy and sexual-health data is special category data under EU and UK GDPR. "Most" is the firm's hedge, not a regulator's finding. Source: https://www.dlapiper.com/en/insights/publications/2026/03/privacy-and-data-security-in-femtech

## Open datasets

| Name | People and samples | Signals and ground truth | Size | Access |
|---|---|---|---|---|
| mcPHASES | 50 enrolled, 42 consented; 42 in 2022, 20 in 2024 | Fitbit Sense, Dexcom G6 (2022 only); Mira LH, E3G, PdG, 4 phases | Not stated | Registered users, signed DUA 1.5.0; files no longer available |
| VISEM-Tracking | 20 wet-prep sperm videos of 30 s, 29,196 frames | Video; manual boxes, expert sperm traits | 6.3 GB zip | Zenodo, CC BY 4.0, open download |
| Embryo time-lapse (Gomez et al.) | 704 videos, 337k images | Images; 16 development phases | 62.8 GB (v2) | Zenodo, CC BY-NC-SA 4.0, open |
| CTU-UHB | 552 intrapartum CTG recordings | Fetal heart rate, contractions at 4 Hz | 38.0 MB | PhysioNet, ODC Attribution 1.0, open |

- mcPHASES: the four phases are menstruation, late follicular, ovulation and luteal, from Mira's own interpretation. No cycle count or total size is on the page. Source: https://physionet.org/content/mcphases/
- VISEM-Tracking: Zenodo record https://zenodo.org/records/7293726 and paper https://arxiv.org/abs/2212.02842
- Embryo time-lapse: the paper is https://arxiv.org/abs/2203.00531 and the Zenodo record is https://zenodo.org/records/7885222. The record is v2 of 28 Mar 2022, and a newer version exists. The annotations file is 53.3 kB. The nine image files are 7.3 to 12.1 GB each, so a small subset means annotations only. The non-commercial licence matters for any product use.
- CTU-UHB: https://physionet.org/content/ctu-uhb-ctgdb/1.0.0/

## Published accuracy for ovulation and fertile-window detection

- Ava bracelet (Goodale 2019, JMIR): 237 women recruited in Zurich, 193 in the final analysis. 1,194 cycles, 708 analysable. A random forest on 11 features (wrist skin temperature, heart rate, HRV, respiratory rate; perfusion measured) found the 6-day fertile window in 90% of cycles (95% CI 0.89 to 0.92), sensitivity 0.81, specificity 0.93, against urinary LH. The 90% is over the validation set only: 85 cycles from 24 users, not all 708 cycles. The interval looks tighter than 85 cycles would support, so it is probably over days. The authors work for Ava and declare a financial conflict. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6495289/
- Ava wrist device diagnostic study: 61 women and 205 cycles in a clinical trial, plus 3,268 real-world users and 6,081 cycles. Mean ovulation error against LH was 0.31 days retrospective and -0.04 days prospective. Fertile days were correctly identified in 75.4% (retrospective) and 73.8% (prospective). The Discussion gives the prospective error as -0.4 against -0.04 in the Results and table, and both confidence intervals span zero. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC10747116/
- Oura finger temperature: 964 members, 1,155 ovulatory cycles, reference is the positive LH test date. Ovulation detected in 96.4% of cycles. Average error 1.26 days against 3.44 days for the calendar method (irregular cycles 1.48 against 6.63 days). The figures come from Oura's own blog summary, written by Oura authors, with self-logged LH tests. The comparison with the calendar method is not like-for-like. Source: https://ouraring.com/blog/oura-ovulation-detection-algorithm-validation-study/
- Apple wrist temperature (JMIR preprint): 260 participants, 889 cycles. A completed-cycle ovulation estimate came in 80.8% of cycles with a signal of at least 0.2 C. Mean absolute error 1.22 days, 89.0% within 2 days. Next menses within 3 days in 89.4%. Source: https://preprints.jmir.org/preprint/50821
- Natural Cycles states a typical-use Pearl Index of 7 and a perfect-use Pearl Index of 2. The global study followed 22,785 participants from 37 countries (typical 6.9, perfect 1). The Pearl Index measures contraception failure, not ovulation-detection accuracy, so do not cite it as accuracy. Source: https://www.naturalcycles.com/research-library/how-effective-is-natural-cycles-as-birth-control

## Hardware found

- A hybrid dual-core CPU plus FPGA sperm motility analyzer prototype exists. Image processing runs on the FPGA and calculations on the CPU. It is video tracking, not a chip-only classifier. Source: https://doaj.org/article/5979ab46318c4ae585a50376a783b7cd

## Looked for and not found

- A published fertility, ovulation or reproductive-health classifier built as a logic gate network or with hard-wired weights. Searches returned only general logic gate network papers.
- A published low-power ASIC or FPGA that computes ovulation or the fertile window on the device. Only old microcontroller thermometer patents turned up, and no peer-reviewed chip design.
- An FPGA-only or chip-only sperm motility classifier. Only hybrid CPU plus FPGA systems turned up.
- An open wearable dataset (temperature or heart rate) with ovulation confirmed by ultrasound. Only mcPHASES, which is LH-based.
- mcPHASES total download size and cycle count.
- Where Natural Cycles, Mira, Apple and Oura compute their outputs (device, phone or servers). Pages opened do not say.
- Ava bracelet sensor, output, FDA status and compute location: the official site was a placeholder.
- Tempdrop, OvuSense, kegg, YO Home Sperm Test and ExSeed were not searched. Inito's own page was not opened.
- Verso Biosense regulatory status and results.
- An EU data-protection authority decision on a fertility or period app.
- Regulator text that names reproductive or fertility data as special category. Recital 35 and the ICO list do not name it.
- Primary-page quotes for the Oura 2025 paper, the Apple Human Reproduction paper and the Natural Cycles 2017 Pearl Index paper. Pages were blocked. Oura figures come from its blog only.
- Original VISEM dataset size and licence.
- Nothing here covers EEG or brainwave data.

## Wording to avoid

- Do not say mcPHASES can be downloaded now (the page says files are no longer available), or that 42 people took part in both intervals (only 20 did in 2024).
- Do not give the Ava 90% as covering 708 cycles or 237 women. It is 85 validation cycles from 24 users, from authors employed by Ava.
- Do not state the ICO launch date as Sep 2023 or say the ICO issued no enforcement as if the page said so.
- Do not say the Premom order was finalized. It was proposed. The data also went to China-based firms.
- Do not use Verso Biosense as the device name, and do not imply the womb sensor is approved or on the market.
- Do not call the law firm's "most" a regulator finding.
- Do not say the Recital or the ICO page names reproductive or fertility data explicitly.
- Do not quote Oura's 96.4% as an independent result, or set the 82%-within-2-days comparison against the calendar method as like-for-like.
- Do not cite the Pearl Index as ovulation-detection accuracy.
- Do not use the embryo record's 62.8 GB without stating its non-commercial licence.
