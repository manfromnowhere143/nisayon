/** A bounded transfer reports bytes actually received. A slow, progressing
 * response is different from a connection that has stopped making progress. */
export interface TransferProgress {
  loaded: number;
  total: number | null;
}

export interface TransferOptions {
  signal?: AbortSignal | undefined;
  maxBytes: number;
  expectedBytes?: number | undefined;
  stallTimeoutMs?: number | undefined;
  timeoutMs?: number | undefined;
  onProgress?: ((progress: TransferProgress) => void) | undefined;
}

export class TransferError extends Error {
  constructor(
    readonly kind: "network" | "absent" | "decode" | "aborted",
    message: string,
  ) {
    super(message);
    this.name = "TransferError";
  }
}

export async function transferBytes(
  url: string,
  fetcher: (url: string, init: { signal: AbortSignal }) => Promise<Response>,
  options: TransferOptions,
): Promise<ArrayBuffer> {
  const controller = new AbortController();
  const stallMs = options.stallTimeoutMs ?? 20_000;
  const totalMs = options.timeoutMs ?? 120_000;
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  let idle: ReturnType<typeof setTimeout>;
  let rejectTransfer: (error: TransferError) => void;
  const interrupted = new Promise<never>((_, reject) => {
    rejectTransfer = reject;
  });
  const stop = (error: TransferError) => {
    rejectTransfer(error);
    controller.abort();
    void reader?.cancel().catch(() => {});
  };
  const abort = () =>
    stop(new TransferError("aborted", "load superseded by a newer selection"));
  const progress = () => {
    clearTimeout(idle);
    idle = setTimeout(
      () =>
        stop(
          new TransferError(
            "network",
            "Download stopped making progress. Please retry.",
          ),
        ),
      stallMs,
    );
  };
  const deadline = setTimeout(
    () =>
      stop(
        new TransferError(
          "network",
          "Download exceeded its time limit. Please retry.",
        ),
      ),
    totalMs,
  );
  options.signal?.addEventListener("abort", abort, { once: true });
  progress();
  try {
    if (options.signal?.aborted) abort();
    options.onProgress?.({ loaded: 0, total: options.expectedBytes ?? null });
    const response = await Promise.race([
      fetcher(url, { signal: controller.signal }),
      interrupted,
    ]);
    if (response.status === 404)
      throw new TransferError("absent", "file not found (HTTP 404)");
    if (!response.ok)
      throw new TransferError("network", `HTTP ${response.status}`);
    const length = response.headers.get("content-length");
    const declared =
      length !== null && !response.headers.get("content-encoding")
        ? Number(length)
        : null;
    if (declared !== null && declared > options.maxBytes)
      throw new TransferError("decode", "response exceeds the byte bound");
    const total =
      options.expectedBytes ??
      (declared !== null && Number.isFinite(declared) ? declared : null);
    if (total !== (options.expectedBytes ?? null))
      options.onProgress?.({ loaded: 0, total });
    progress();
    if (!response.body) {
      const bytes = await Promise.race([response.arrayBuffer(), interrupted]);
      if (bytes.byteLength > options.maxBytes)
        throw new TransferError("decode", "response exceeds the byte bound");
      options.onProgress?.({ loaded: bytes.byteLength, total });
      return bytes;
    }
    reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let loaded = 0;
    for (;;) {
      const chunk = await Promise.race([reader.read(), interrupted]);
      if (chunk.done) break;
      if (!chunk.value.byteLength) continue;
      loaded += chunk.value.byteLength;
      if (loaded > options.maxBytes)
        throw new TransferError("decode", "response exceeds the byte bound");
      chunks.push(chunk.value);
      options.onProgress?.({ loaded, total });
      progress();
    }
    const bytes = new Uint8Array(loaded);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return bytes.buffer;
  } catch (error) {
    if (options.signal?.aborted)
      throw new TransferError(
        "aborted",
        "load superseded by a newer selection",
      );
    if (error instanceof TransferError) throw error;
    throw new TransferError(
      "network",
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    clearTimeout(idle!);
    clearTimeout(deadline);
    options.signal?.removeEventListener("abort", abort);
    controller.abort();
    void reader?.cancel().catch(() => {});
  }
}
