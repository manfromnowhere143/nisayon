# Correct the published inventory, preserve the failed readback

The initial public commit `b3eb4e5239f8b96511d3e8b816b877f21c81ebf4`
accidentally listed four ignored Python bytecode cache files in `manifest.json`.
They existed during local replay but were not in the committed Git tree. A local
filesystem hash check passed, while the post-publication Git-object check found
the inventory invalid. No upstream review had been delivered at that point.

The correction removes those unshipped cache entries and generates the inventory
from versioned files. `verify_git.py` checks both complete member coverage and
bytes directly from the selected Git commit. It rejects the initial commit and
accepts the corrected one. This tests the exported object set rather than local
cache availability. It does not authenticate experiment truth.

Native source, probe implementation, observations, failed tests, effect journals,
cost records and their scientific conclusions are unchanged. The error was in
publication packaging. The initial commit remains in public history; its manifest
must not be treated as valid. This correction adds no scientific success or
economic benefit claim.
