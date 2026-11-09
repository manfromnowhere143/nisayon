// SHA-256 of fetched bytes through WebCrypto. The digest is computed on the
// exact bytes that are then parsed; nothing is re-serialized in between.

export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new Error("WebCrypto SHA-256 is unavailable in this context; serve the instrument over http://localhost or https");
  }
  const digest = await subtle.digest("SHA-256", bytes);
  let out = "";
  for (const byte of new Uint8Array(digest)) out += byte.toString(16).padStart(2, "0");
  return out;
}
