# Primary research informing the owner-effort measurement

Read 24 October 2026. These sources inform measurement and its limitations; no
paper's experiment was reproduced here. Publication in 2026 does not imply its
observations concern the latest models. This review supports a prospective
measurement design, not a claim that Nisayon has the best method in the field.

| Source and exact version | Finding relevant to this experiment | Decision and boundary |
|---|---|---|
| METR, [We are Changing our Developer Productivity Experiment Design](https://metr.org/blog/2026-02-24-uplift-update/), 24 February 2026 | Wider AI adoption introduced selection, task-mix and completion differences; concurrent agents make elapsed time a poor proxy for developer effort. | Register eligible decisions and assignments before outcomes, retain incomplete work, and record active human intervals separately. Both Nisayon and the competent native baseline get capable agent access. Do not import an AI-versus-no-AI effect. |
| Whitfill et al., METR research note, [Many SWE-bench-Passing PRs Would Not Be Merged into Main](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/), 10 March 2026 | Four maintainers reviewed patches across three repositories; automated success and maintainer acceptance differed. The study used older agents and hypothetical reviews with restricted iteration and CI. | Separate software correctness from the owner's acceptance of the delivered decision. Allow both workflows equal feedback and charge all rework. Neither a test pass nor a model's review is an owner receipt. |
| Zhong et al., [Human-AI Synergy in Agentic Code Review](https://arxiv.org/html/2603.15911v1), arXiv:2603.15911v1, 16 March 2026 | Observational analysis of 278,790 conversations across 300 projects, using 2022–2025 records, reports different suggestion adoption and interaction patterns. Automated classifications and file metrics have limits. | Record actual review activity, questions and rework. Comment count and static metrics are not measured minutes or causal savings. The reported patterns do not establish present-day robotic integration performance. |
| He et al., [AI Writes Faster Than Humans Can Review: A Longitudinal Study of an Enterprise “2×” Mandate](https://arxiv.org/html/2607.01904v1), arXiv:2607.01904v1, 2 July 2026 | One firm's observed throughput growth coincided with greater review load. The authors distinguish an observational adoption association from a clean causal effect and note downstream costs beyond merging. | Charge review, adoption and a fixed maintenance horizon. Preserve owner and engineering effort separately so shifting work does not resemble savings. A throughput ratio from one firm does not establish Nisayon's twofold complete-cost target. |

The implementation follows from these concerns: a simple explicit timer, full
phase coverage, retained interruptions, monetary valuation only with supplied
receipts, and a separate owner acceptance gate. More model selection machinery
would not resolve the current missing observation: what a real owner actually
had to do to reach and accept the decision.
