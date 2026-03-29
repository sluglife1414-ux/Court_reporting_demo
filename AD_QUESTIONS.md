# AD QUESTIONS — ALICIA D'ALOTTO
# Questions we need answered before Fourman can ship clean
# and before we can lock in her house style module.
#
# PM: surface these to Scott at next touchpoint with AD.
# Code Claude: do not guess on these — wait for answers.
# Last updated: 2026-03-30

---

## STATUS SUMMARY

| Item | Status |
|------|--------|
| Claimant name | ✅ JAMES K. RUFFLER SR. (from AD reference PDF) |
| Employer | ✅ IRVINGTON UFSD (from AD reference PDF) |
| WCB Case No. | ✅ G395 3702 (from AD reference PDF) |
| Carrier Case No. | ✅ PRMA216578 (from AD reference PDF) |
| D/A | ✅ October 10, 2024 (from AD reference PDF) |
| Depo time | ✅ 4:03 p.m. (from AD reference PDF) |
| Reporter name | ✅ ALICIA D'ALOTTO (confirmed from cert page) |
| Notary title | ✅ Notary Public of the State of New York |
| Reporter address | ✅ 89 Lincoln Street, Staten Island, New York 10314 (from reference PDF) |
| Reporter phone | ✅ 732-713-9869 (from reference PDF) |
| Claimant atty firm | ✅ O'CONNOR LAW PLLC, 7 Woodland Ave Suite 10, Larchmont NY 10538 (from reference) |
| Claimant atty by | ✅ TIMOTHY BLUM, ESQ., of Counsel (from reference) |
| Respondent atty firm | ✅ STEWART GREENBLATT MANNING & BAEZ, 6800 Jericho Tpke Suite 100W, Syosset NY 11791 |
| Respondent atty by | ✅ BARRY FRIEDLICH, ESQ. (from reference) |
| NY state config | ✅ All layout values measured from reference PDF via pdfplumber (2026-03-30) |
| Caption page format | ✅ Reporter contact on page 1 lines 24-25 (matches reference) |
| Notary reg. # | 🔴 PLACEHOLDER (01DA6000000) — need real number |
| Cert page structure | 🔴 UNKNOWN — does she have one? (see Q2 below) |
| Sample finished depo | 🔴 Q3 CLOSED — we used Fourman reference PDF directly (better than asking!) |
| Credential letters | 🔴 UNKNOWN — RPR? CCR? None? |

---

## OPEN QUESTIONS FOR AD

### Q1 — Notary Registration Number
**What we need:** Her NY notary public registration number.
**Where it goes:** Cert page, line below her signature: `Notary Registration No. XXXXXXX`
**Current placeholder:** `01DA6000000` — do not ship this.
**Format:** NY notary numbers look like `01XX6000000` (2 digits + initials + digits)

---

### Q2 — Cert Page Structure
**What we need:** Does she include a formal `C E R T I F I C A T E` page in her WC depos?
**Context:** Our engine builds a separate cert page (page 23 in Fourman output) with:
  - Her notary certification language
  - Her signature line
  - Her name
Scott's note (2026-03-29): "there is no cert page in final — it her sig then appearances"
**Interpretation needed:** Is the cert language embedded differently? Or omitted entirely?
**Impact:** If no cert page → remove `build_notary_cert()` from NY WC format pipeline.

---

### ~~Q3 — Sample Finished Depo~~ ✅ CLOSED 2026-03-30
We measured the Fourman reference PDF (0324Fourman2026wcbG3953702.pdf) directly with pdfplumber.
All layout values are now exact (not estimated). See HOUSE_STYLE_MODULE_dalotto.md for locked values.
Remaining unknowns: cert page language (Q2), notary reg # (Q1).

---

### Q4 — Credential Letters
**What we need:** Does she carry any credential designation? (RPR, CCR, CSR, etc.)
**Context:** Nothing visible after her name in the Fourman reference PDF cert page.
**Impact:** If none → keep `reporter_name` as `ALICIA D'ALOTTO` (no suffix).
**If yes:** Update `reporter_name` in depo_config.json for all her depos.

---

### Q5 — Appearances Page Format
**What we need:** Does she use `xxxxx` as the end-of-appearances marker?
**Context:** Our engine outputs `xxxxx` on the last line of the appearances page.
**Why it's there:** Standard NY court reporter marker. But it's hardcoded — if AD doesn't use it, remove it.

---

### Q6 — Word Concordance
**What we need:** Does she want the word concordance pages in her final transcript?
**Context:** Fourman output has 7 pages of word concordance (pages 24-30).
  Format: 3-column, word + page references.
**If no:** Remove `build_word_concordance()` from her pipeline config.
**If yes:** Confirm the column layout matches her format.

---

### Q7 — Firm Info
**What we need:** Her agency/firm name, address, and phone — if she wants it on the transcript.
**Where it goes:** Appearances page header, caption, or elsewhere depending on her format.
**If solo freelancer:** May not have firm — just her name is fine.

---

## HOW TO CLOSE THESE OUT

When AD answers, update `depo_config.json` in the Fourman folder:
```json
{
  "reporter_license": "[her real number]",
  ...
}
```

Then run: `python run_pipeline.py --from format`

For structural questions (Q2, Q5, Q6): update `format_final.py` accordingly.
For Q3 (sample depo): run `pdfplumber` measurements → update `HOUSE_STYLE_MODULE_dalotto.md`.

---

## PM ROUTING NOTE

These questions should go to AD through Scott.
Do not contact AD directly.
Once answers come back, Code Claude can resolve all of these in a single `--from format` rebuild.

---
*Created: 2026-03-29*
*Owner: Scott / PM Claude*
*Resolved by: Code Claude (after answers received)*
