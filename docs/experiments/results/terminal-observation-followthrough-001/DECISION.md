# N031: submit the terminal-observation correction separately

12 October 2026 · selected after an external reply, before new validation.

## Evidence and decision

[LinCanNerd's reply](https://github.com/huggingface/lerobot/pull/4932#issuecomment-6129880034)
agrees that N023's recording defect predates PR #4932 and belongs in a separate
contribution. They offer to test it on Jetson Thor after publication. This is an
offer from that PR's author, not a maintainer acceptance or completed replication.
[N023](../async-eval-qualification-001/README.md) retains the original native
reproduction, patch, successful combined checks and invalid attempts.

The consequential next step is a focused upstream contribution, rebased onto
current LeRobot `24f15b92b556cb861ca65e989462e23505a701bd`. Alternatives are
leaving the patch in the review, stacking unrelated worker/scoring corrections,
or continuing another source audit. A separate patch makes review and the
offered external test possible without claiming those other corrections.
N030's original control results remain preserved; its candidate is deferred.

Gymnasium SAME_STEP returns reset observations for live execution and places
terminal observations in `info["final_obs"]`. The stored completed episode must
end at the terminal observation, including nested image data. Live inference
must continue receiving the returned reset observations. Existing upstream
PR #4485 owns the separate scoring correction; do not copy or claim it here.

## Experiment, resources and acceptance

Inspect the selected base and contribution instructions. Reuse N023's locked
CPU environment without modifying it; bind actual imported source and package
versions. Use deterministic, action-dependent Gym tasks and a scripted policy,
including SyncVectorEnv and real AsyncVectorEnv workers, termination and
truncation, SAME_STEP and NEXT_STEP, state and nested RGB observations. Compare
recording enabled and disabled to check live inference, actions and metrics.
Retain the unchanged baseline failures before executing the patch. These are
development regressions, not fresh independent policy confirmation.

Reject the diagnosis if current source already retains the true last frame.
Reject a candidate if an expected sequence, live input, action, metric or existing
relevant test changes incorrectly. Run the relevant upstream tests and configured
lint/format checks. Keep unrelated failures visible. Do not import #4485 or #4932
to obtain passing terminal-only results. A successful correction must fail its
targeted SAME_STEP recording controls on the unchanged base, pass all declared
controls with the patch, preserve NEXT_STEP behavior and require no GPU, learned
checkpoint, simulator or robot.

Resources: existing CPU environment, one new isolated source checkout, under
four engineering hours. No dependency synchronization or hardware operation.
Publish only the reviewed upstream patch and tests with Daniel's verified Git
identity, then send one concise reply linking the contribution and exact test
command. Retain publication/readback and costs. External reproduction, upstream
adoption and N015's comparative economic value remain unresolved.
