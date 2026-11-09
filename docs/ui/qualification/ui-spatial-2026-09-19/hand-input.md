# Camera hand input: defer until there is an experiment

19 September 2026. Recommendation, not an implemented capability.

Do not add webcam mirroring to the present recorded instrument. Nisayon's job
is to distinguish integration failures and confirm corrections. Hand tracking
would be aligned when it supplies demonstrations, human recovery interventions,
or a controlled input stream for a specific experiment. None of the current six
recorded cases requires it. This is a scope judgment from the
[architecture](../../../ARCHITECTURE.md), not a claim that hand teleoperation is
technically infeasible.

Existing systems already separate demonstration collection from policy training.
[Isaac Lab 2.3.1](https://isaac-sim.github.io/IsaacLab/v2.3.1/source/overview/imitation-learning/teleop_imitation.html)
supports teleoperation, recorded demonstrations and subsequent imitation-learning
workflows, including hand-to-robot retargeting. [LeRobot's HIL collection](https://huggingface.co/docs/lerobot/hil_data_collection)
records policy and human intervention segments for later fine-tuning. Its
documented DAgger integration has specific motorized teleoperator requirements;
it is not a plug-and-play webcam path.

A future useful slice would map a calibrated hand-relative input to a simulated
end-effector target and gripper aperture, retaining input timestamps, tracking
loss, mapping version, intended/executed actions, operator handoffs and task
outcome. The current Panda has a parallel-jaw gripper; it cannot copy the full
anatomy of a human hand. [MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
provides hand landmarks, but this alone does not establish a calibrated robot
workspace frame or a reliable manipulation controller. Reuse an existing tracker
and retargeter before considering a bespoke perception stack.

The reason to build it would be a declared question: for example, whether human
recovery demonstrations improve a frozen candidate's autonomous task completion
on fresh conditions at lower total cost than a competent baseline. Record first,
train a separately versioned candidate, then evaluate without human assistance.
Hand-mirrored success is teleoperation, not evidence that the robot learned.
Tracking dropout and latency need to remain observable, and changed commands
require newly executed future states.

No camera capture, hardware control, training or new scientific trial is added
by this review. The first implementation, if justified by such an experiment,
belongs in a separately qualified simulation adapter feeding the same evidence
and confirmation workflow. The current priority remains inspectable experiments.
