# V5 2014 — protocol execution note

## Discarded run

GitHub Actions workflow run `34515712020` was launched from commit `a442d02d04b182a5903a0d616e015eb0ae717c6f`.

Its market outcome was **not inspected or used for a research decision**.

After launch, code review identified a reporting/protocol mismatch in `scripts/run_fxcm_2014_v5_histgb.py`: the helper responsible for locked-slice robustness diagnostics ran whenever a locked test existed, including a `failed_locked` result. The preregistration states that robustness diagnostics are permitted only after a **passed locked test**.

This mismatch does not alter development candidate selection, validation gating, or the primary locked pass/fail calculation. However, it could expose additional post-hoc information from a failed locked slice earlier than allowed by the frozen protocol. For that reason the entire run is designated:

**DISCARDED — DO NOT INTERPRET, CITE, OR REGISTER ITS PERFORMANCE OUTPUT.**

No performance numbers from this run were read before this designation was recorded.

## Correction

Commit `c0ffd891e1e7e034f4021488a434095b9f4fbc97` changes the reporting helper so it returns robustness diagnostics only when `experiment.status == "passed_locked"`. A passed-locked state missing its candidate or locked result now raises an error rather than silently continuing.

The preregistered model, feature set, hyperparameters, expiry grid, confidence thresholds, chronological split, development eligibility, validation gate, and locked-test gate are unchanged.

A new workflow run triggered from the corrected commit is the only V5 2014 result that may be interpreted.

## Data-status clarification

The discarded automation may have downloaded or processed 2014 data internally before the mismatch was noticed. No resulting performance output was inspected by the research decision-maker. Therefore 2014 remains usable for the same already-preregistered V5 protocol rerun, but it must not be treated as a new independent dataset after that corrected result is observed.

FXCM 2015 remains untouched and is still reserved exclusively for no-tuning replication if—and only if—the corrected V5 2014 locked test passes.
