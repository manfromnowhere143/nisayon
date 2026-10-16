@cjd-hub @ravediamond — is this still blocking an Orin deployment? @ravediamond, you mentioned already running the FP32 and decoder checks. I can review those existing results and help narrow the next step before you spend time changing the stack.

One detail to preserve when interpreting the FP32 test: in [v0.4.2, `use_amp=False` only disables the autocast context](https://github.com/huggingface/lerobot/blob/58f70b6bd370864139a3795ac3497a9eae8c42d5/src/lerobot/utils/control_utils.py#L100-L111). It does not convert the model parameters. The [VLM loading branch explicitly requests bfloat16 when `load_vlm_weights=True`](https://github.com/huggingface/lerobot/blob/58f70b6bd370864139a3795ac3497a9eae8c42d5/src/lerobot/policies/smolvla/smolvlm_with_expert.py#L76-L87). The actual parameter dtypes therefore matter; the flag alone cannot establish an FP32 comparison.

LinCanNerd's script already includes `policy.float()` and fixed observation/noise controls. That is useful groundwork. Its Thor numbers remain specific to that setup; they do not settle the original Orin failure.

If the decision is still live, a link or pasted output from your existing Orin checks, the code/checkpoint revisions, and whether the test used `policy.float()` would be enough for a first pass. Please also say which choice is blocked—for example, correcting local inference or moving serving to the working host. I can start from those records; no new runs or private weights are needed for that review.

I’m developing [Nisayon](https://github.com/manfromnowhere143/nisayon) to test whether this kind of diagnosis saves engineering work. This source review used AI assistance; I have not reproduced the failure on Orin.
