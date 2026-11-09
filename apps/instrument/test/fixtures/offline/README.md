# Legacy offline worker

`cache-first-worker.js` is retained byte-for-byte from Nisayon commit
`6f79dc18`, path `apps/instrument/src/pwa/worker.js`.
SHA256: `baed026ca5203e03d667e4a9fdf2ff11c8e8690bdf498db3439a98e0ee8013eb`.
It reproduces the shipped cache-first navigation and waiting lifecycle.
Tests supply a small hashed release; they do not claim a browser installation.
