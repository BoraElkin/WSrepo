# Submission — AI Immigration Case Manager

## 1. Written Explanation

**What the human can now do that they couldn't before.**

An immigration lawyer can go from a raw client intake to a complete case brief in under two minutes. Before this tool, that process — cross-referencing eligibility criteria across four pathways, building a document checklist, identifying risk flags, estimating timelines — takes one to three hours of paralegal time per case. The AI compresses that into a single API call. The lawyer now spends their time on judgment, not assembly. They review a structured brief instead of building one from scratch. That means more clients seen per day, faster turnaround for the client, and fewer details falling through the cracks.

**What AI is responsible for.**

The AI handles five things: eligibility assessment across Express Entry, Spousal Sponsorship, Post-Graduate Work Permit, and Intra-Company Transfer pathways, ranked by likelihood of success. A complete document checklist flagged by status. Risk flags that surface inconsistencies or red flags an immigration officer might scrutinize, with severity ratings and suggested mitigations. An estimated timeline with milestones. And a case summary written in professional language ready for a lawyer's file. All of this is generated from structured client intake data sent as JSON to Claude, with a system prompt that enforces conservative analysis and prohibits direct legal advice.

**Where AI must stop.**

The AI never approves a case. Screen 3 exists specifically to enforce this. The lawyer must either click "Approve Case Brief" or "Flag for Manual Review" before anything moves forward. This isn't a soft recommendation — it's a hard gate in the application flow. The AI frames every finding as something "the lawyer should consider." It does not tell a client they qualify. It does not recommend filing. It does not generate submission-ready forms. The disclaimer on every review screen makes this explicit: the analysis must be reviewed by a licensed immigration professional before any action is taken. The AI is the paralegal. The lawyer is the lawyer.

**What would break first at scale.**

Trust calibration. The system works when a lawyer reads every brief carefully. At scale — hundreds of cases per day across a firm — the risk is that lawyers start rubber-stamping approvals because the AI is "usually right." The green Approve button becomes a reflex instead of a decision. The fix isn't technical; it's operational. You'd need random audits, mandatory review time minimums, or a periodic "challenge case" where the AI intentionally includes a subtle error the lawyer must catch. The second thing that breaks is prompt brittleness — edge cases in immigration law (humanitarian and compassionate grounds, criminal inadmissibility, complex family sponsorship chains) will produce confident-sounding analysis that misses critical nuance. The system needs a feedback loop where flagged cases improve the prompt over time. Without that, the AI's confidence becomes a liability rather than an asset.

---

## 3. Salary & Experience

**Salary expectation:** 65000-75000

**Years of hands-on experience with AI tools or systems:** 2 Years of Experience

---

*No decks. No resumes.*
