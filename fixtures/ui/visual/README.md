# Optional display geometry

The current package is pinned in
`apps/instrument/src/scene/visualAssetPin.ts`. It contains the Panda, gripper and
mount display meshes compiled from the already admitted robosuite 1.4.1 model
sources with MuJoCo 3.2.7. It adds no experiment or physical execution.

Current SHA-256: `0832558ac5fdf88fb92c31d54a88f93987c31825680cef2a79009669c56433a2`
(13,772,768 bytes). The 54 parts share 53 meshes with 344,642 vertices and
167,252 triangles. Only identical position/normal corners are joined; source
vertices, normals, hard edges and compiled local transforms are retained.
Earlier package objects remain available for earlier qualification records.

The browser verifies package bytes, the selected model JSON digest, XML source,
asset digests and body order before displaying the detailed surfaces. Missing or
mismatched optional geometry leaves the qualified schematic and original readings
available. Decoding runs in a worker; primary and comparison figures share buffers.

[ROBOSUITE-LICENSE.txt](ROBOSUITE-LICENSE.txt) is the exact license from the
installed robosuite 1.4.1 distribution, SHA-256
`cbc6f509c69f14e2e801f4e6506bc263b00fa4e3ec2b70d428a5ea0a9c676853`.
It retains Stanford Vision and Learning Lab / UT Robot Perception and Learning
Lab copyright and the included MuJoCo notice. The package records the
[upstream versioned license](https://github.com/ARISE-Initiative/robosuite/blob/v1.4.1/LICENSE)
and exact local inputs; no unverified upstream commit identity is asserted.

From the UI worktree, using the existing execution environment read-only:

```sh
/Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python tools/ui/export_visuals.py
```

See [native qualification](../../../docs/ui/qualification/native-visuals.json).
The numerical checks concern geometry binding, not image quality. Materials,
studio illumination, shadows and wall cutaways are display treatments, not
recorded camera images, contact evidence or additional lab hardware.
