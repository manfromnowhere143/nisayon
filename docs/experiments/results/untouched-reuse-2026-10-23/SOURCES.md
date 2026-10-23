# Sources used for the comparison boundary

Checked 23 October 2026. These sources inform the protocol; their experiments
were not reproduced and they do not establish Nisayon's superiority.

- Atinafu and Cohen, [RewardHackingAgents, arXiv:2603.11337v1](https://arxiv.org/html/2603.11337v1),
  11 March 2026. Separates evaluator tampering and held-out answer access.
  Applied here through protected evaluator files, denied cross-workspace reads
  and a requirement to observe access failures before claiming isolation.
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents),
  9 January 2026. Distinguishes execution traces and final outcomes and explains
  how shared trial state can contaminate results. Applied through fresh contexts,
  frozen artifacts and deterministic native grading where the semantics permit it.
- Anthropic, [Quantifying infrastructure noise in agentic coding evals](https://www.anthropic.com/research/infrastructure-noise),
  5 February 2026. Resource configuration affects observed agent performance.
  Applied through matched host, dependencies and budgets and explicit cache costs.
- OpenAI, [Permissions](https://learn.chatgpt.com/docs/permissions) and
  [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
  current documentation accessed 23 October. Named profiles support explicit
  filesystem grants and network policy. Local qualification binds CLI 0.163.0
  and its executable hash; documentation alone is not the test result.
- OpenAI, [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),
  current documentation accessed 23 October. JSON events expose completed-turn
  token usage. `--ephemeral` and `--ignore-user-config` are also present in the
  installed CLI help. Counts and a successful process exit do not attest either
  provider charges or experimental quality.

An attempted older infrastructure-noise URL returned an error. The canonical
research URL above was subsequently located and read. No scientific conclusion
depends on the inaccessible URL or a secondary mirror.
