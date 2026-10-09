# Historical replay during the engine continuation

The archived scripted and bounded-model scorers both reproduced their complete
original score documents exactly on 19 September 2026. The scripted result
remains 6/10 incidents per arm and the bounded-model result remains 3/3 repetitions
of one exposed D07 incident per arm. No efficiency advantage or new evidence is
inferred. The retained files are [scripted score](scripted-score.json),
[bounded score](bounded-score.json) and the separately labelled
[current-source identity audit](current-audit.json).

Before execution, both compressed archives and every regular file were checked
against `reproduction/sources/manifest.json`. The first extraction check counted
directory entries as files and failed; command
`868c21e8e8604901b9ce3aa673290f7b` preserves that failure. The corrected check
distinguishes directory entries while still rejecting links and path traversal.
It verified all 63 scripted and 70 bounded-source files. No archive bytes were
changed. The corrected command was `fef91b78bc1b444ea48cb820826c9bad`.

Original scripted execution/evaluator revisions:
`a9984af39c89e6aacf8c65fd3a7db6cb05c5eca8` /
`90767cd2443eb9f129631e310743d01ee8c77b4d`.
Original bounded execution/evaluator revisions:
`f97aa1722966667e1de5ddcf5f261d2c605dae88` /
`6e112c49b152f9b475660ab18d1ad5c0459129aa`.

Commands `5fa9a908aba34f258b149d9e04876b90` and
`85752bab73d44d6199cc86db7f8cbdf4` used those archived source directories through
explicit child-process `PYTHONPATH`; walls were 0.184581 s and 1.963355 s.
The current audit `6c0020ef19b34b96b14fda581715b944` took 9.305865 s. These are
new replay-processing costs, separate from historical experiment costs.
No simulator or model calls occurred.
