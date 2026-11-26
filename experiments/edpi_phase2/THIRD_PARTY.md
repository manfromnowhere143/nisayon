# Source and asset boundaries

The serving source copies come from Hugging Face LeRobot commit
`b07adcc5e3ce42c26a248236dbb3571f84c28c43`. Its
[Apache-2.0 license](serving/upstream/LICENSE) and original source notices are
preserved. [LeRobot #5525](https://github.com/huggingface/lerobot/issues/5525)
supplied the external report; this work does not claim that report as its own
discovery, an owner enrollment or upstream approval of the proposed patch.

Only configuration metadata for `lerobot/pi05_libero_finetuned_v044` at
`7152f13e34c6c115d808aea0e5d08aca74eac14b` was acquired. No model weights are
included. Model licensing and permission to run a future learned-policy study
must be assessed separately; this source release grants none.

The physical producer depends on the publicly distributed robosuite 1.5.1 and
MuJoCo 3.2.7 stack. Generated XML and numeric observations preserve the recorded
configuration; robot meshes, textures, installed distributions and the compiled
MJB are not distributed here. Existing [project licensing boundaries](../../docs/LICENSING.md)
and [dependency notices](../edpi_finite/evidence/dependency-licenses.json) remain
applicable. The native environment must provide the named assets and licenses.

Nisayon's original source follows the repository license. Source hashes,
dependency versions and factual tool provenance remain in the records. They
establish neither authorship of upstream work nor scientific acceptance.
