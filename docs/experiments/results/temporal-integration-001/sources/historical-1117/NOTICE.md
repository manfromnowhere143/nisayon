# Historical LeRobot source packet

The unmodified source files in this directory come from Hugging Face LeRobot,
under the copyright notices at the top of each source file and the Apache 2.0
terms retained in `parent-license.txt` and `fixed-license.txt`. The `.txt` suffix
keeps repository formatters from changing these exact upstream source bytes.

- Fixed revision: `6163daaaa4fa193d0e37468a94d90e07ef3c95ce`.
- Its actual first parent: `8e2a39444255d62869d2fd63ea4f8a157236a029`.
- [Issue 1116](https://github.com/huggingface/lerobot/issues/1116) and
  [PR 1117](https://github.com/huggingface/lerobot/pull/1117) are exposed public
  development sources and a known remedy.

`retrieval.json` binds URLs, byte lengths and SHA-256 digests. The actual patch
adds `policy.reset()` at control-loop entry. The caller, ACT implementation and
licence bytes are identical at the two retained revisions. The PR base named
in its metadata is not this merge's immediate parent.

The Nisayon driver compiles only named reviewed functions from these files;
its extraction record lists source spans, omitted decorators and unchanged
function-body hashes. No upstream module, policy constructor, weights, learned
forward pass, network server, device or hardware interface is started. Scripted
doubles replace tensors, normalization, chunk production, datasets and robot
calls. This qualifies the exercised software lifecycle, not robot performance
or the omitted cleanup/autograd behavior. Upstream attribution is retained;
Nisayon's driver and controlled schedules are separate work.
