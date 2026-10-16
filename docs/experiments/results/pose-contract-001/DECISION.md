# Qualify the meaning of an interface before adding another one

**12 October 2026 · N026, frozen before execution.**

N025 establishes external adoption of one correction. It does not establish
Nisayon product adoption or cheaper decisions. The scientific bottleneck remains
a consequential change with known outcomes and a competent complete-cost
comparator. Daniel requests fresh research and a substantive next step.

## Evidence and alternatives

| Primary source | What it changes in this decision |
|---|---|
| [NVIDIA GR00T 1.7 workflow, 7 July](https://developer.nvidia.com/blog/develop-humanoid-robot-policies-end-to-end-with-nvidia-isaac-gr00t/) | Released models, export paths, training and closed-loop simulation already form an integrated workflow. Another general runtime has a strong incumbent. |
| [Gemini Robotics 2, 30 July](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/) | The model stack includes progress reasoning, adaptation and coordination. These vendor-reported capabilities were not replicated here; Nisayon cannot claim them as an unoccupied category. |
| [Figure Helix 2.5, 17 September](https://www.figure.ai/news/helix-2-5-zero-shot-30-home-generalization) | Reports three task-specific checkpoints tested across 30 unseen homes, fixed success rules and a pretraining ablation. Zero-shot refers to homes/objects; task fine-tuning remains. This is stronger evaluation practice to match, not a released comparator we can reproduce locally. |
| [Physical Intelligence pi0.7 v2, 24 April](https://arxiv.org/html/2604.15483v2) | Context conditioning includes strategies and subgoals. Qualification must bind the actual deployed inputs and transformations, not just a checkpoint name. |
| [XPolicyLab v1, 10 August](https://arxiv.org/html/2608.09892v1) | Supplies isolated serving, 42 reported integrations and adapter checks. Its six-person, counterbalanced study reports lower time to first rollout; residual familiarity and excluded downloads limit interpretation. Treat it as a serious conventional alternative. |
| [Metamorphic VLA testing v1, 26 February](https://arxiv.org/html/2602.22579v1) | Relational checks complement task outcomes. Its trajectory thresholds were manually calibrated and violations need not be task failures. Use an exact declared software relation here; do not import a trajectory-distance threshold as a physical guarantee. |

A new foundation model, simulator, general adapter layer or active selector
would require evidence and resources this result does not supply. Repeating
Arisole's exposed controls again would not establish an advantage. The best
bounded step is to qualify one semantic contract inside the released alternative.

## Hypothesis and falsifying experiment

At XPolicyLab `f6e309e8ece20bfa33c0e5d7b05a5f3287522757`, the README and native
debug validator specify seven values for `ee_pose`: position plus quaternion.
`utils/process_data.py` instead sizes these fields with `arm_dim`, the joint
count. Hypothesis: valid Cartesian inputs are rejected for six-joint arms,
while malformed six-value poses can pass a helper-only round trip. An alternative
is that the shared helper has a consistent different contract; compare it with
the published schema and the unchanged native debug validator before accepting
the defect explanation.

Freeze 22 controls: 12 valid Cartesian cases across four arm layouts and three
array layouts; six existing joint-space controls; four malformed-pose cases.
Use nonzero, distinguishable coordinates and explicit expected concatenation.
Check input preservation, exact values/order, pack/unpack equivalence and native
pose validation. Seven-joint Cartesian cases control for the coincidental
equality of joint count and pose width. Joint controls use the existing dual-arm
names; the separately noticed single-arm joint-name discrepancy is unallocated.

First run the unchanged imported helper. Reject the hypothesis if valid
Cartesian cases meet the published contract and malformed cases are rejected.
If the defect is supported, change only Cartesian field widths to seven in a
separate source copy. Accept that correction only if all 22 controls pass and
joint-space bytes, key order and error behavior remain intact. Retain original
failures, full source hashes and command costs. Ordinary source inspection can
find this mismatch too; this is not a blinded diagnostic-efficiency comparison.

## Resources, milestone and limits

Use one new hashed Python environment with NumPy, OpenCV, h5py and PyYAML, normal
imports from the pinned source, and local CPU arrays. No policy checkpoint,
model inference, simulator, GPU, hardware or reserved evaluation condition.
Cap this incident at four engineering hours. Do not build a generic checker.

The milestone is a source-bound interoperability result and, if supported, one
minimal correction with an executable reproduction delivered to the maintainer
under standing technical follow-through authority. Check live issues and source
before delivery. It would establish added coverage of this specific helper,
not superior robot performance, a novel testing method or savings over the
strongest engineer. N015 and the broader physical-AI mission remain open.
