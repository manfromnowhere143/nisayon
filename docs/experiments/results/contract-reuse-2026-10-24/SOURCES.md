# Primary-source review, 24 October 2026

These papers and announcements inform the experiment design. Their reported
results have not been reproduced here. They do not establish Nisayon's savings.

| Source and version | Relevant finding | Design implication and limit |
|---|---|---|
| [ContractSkill, arXiv:2603.20340v1](https://arxiv.org/html/2603.20340v1), 20 March 2026, §§3–8 | Executable preconditions, step checks and localized repair improved web-agent results in the reported experiments. Transfer reused repaired artifacts within benchmark families. | Freeze executable semantics and applicability, not only instructions. The browser domain is different. The transfer subsets were selected using prior source-model success; reported zero live reuse tokens exclude prior artifact creation. Neither detail supports a complete-cost claim on untouched incidents. |
| [Subagents vs Agent Skills, arXiv:2609.09233v1](https://arxiv.org/html/2609.09233v1), 7 September 2026, §§3–4 | Clear input/output contracts helped subagent execution on the paper's synthesized packages, with more total communication tokens. Packages came from successful trajectories on 64 of 87 SkillsBench tasks. | Encapsulation can help, but additional agents are not intrinsically cheaper. Both execution modes must share content. Package-content comparisons were not controlled, and the selected successful-task subset does not establish generalization to a new physical-AI incident. |
| [NVIDIA Isaac platform announcement](https://nvidianews.nvidia.com/news/nvidia-advances-isaac-platform-for-general-purpose-robotics-with-new-reference-humanoid-frameworks-simulation-pipelines-and-data/), 21 October 2026 | NVIDIA announced Isaac Lab 3.0 and an Isaac OS runtime alongside learning, simulation and robot-reference workflows. | Our inference: another broad runtime/interface has no demonstrated differentiation. Test whether Nisayon reduces the effort of a valid change decision on existing stacks. An official announcement is evidence of positioning and availability claims, not independent measured superiority. |

The new decision is therefore to qualify one small reusable contract, then seek
an untouched applicable incident before building a larger contract library,
dependency graph or adaptive selector. A negative applicability result is useful
evidence about the reach of the current contract.
