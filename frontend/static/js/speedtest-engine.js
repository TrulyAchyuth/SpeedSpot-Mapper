// Wrapper around M-Lab's ndt7 client (vendored in /static/vendor/ndt7). Swapping the
// engine later only means changing this file.
//
// - Download/upload: mean throughput over each ~10 s test.
// - Response time: the connection's minimum round-trip time (TCP MinRTT) seen by the server.
// - Stability: TCP round-trip-time variation (RTTVar) — an approximation of jitter.

export const ENGINE_ID = "mlab-ndt7";

const WORKERS = {
  downloadworkerfile: "/static/vendor/ndt7/ndt7-download-worker.js",
  uploadworkerfile: "/static/vendor/ndt7/ndt7-upload-worker.js",
};

const serverUploadMbps = (tcp) =>
  tcp?.BytesReceived && tcp?.ElapsedTime ? (tcp.BytesReceived * 8) / tcp.ElapsedTime : null; // bytes·8 / µs = Mbit/s

export class TestCancelled extends Error {}

/**
 * Cancelling: ndt7-js has no cancel API, so while a test runs we track the Web Workers it
 * creates and terminate them (which closes their connections to M-Lab).
 */
let activeWorkers = [];
let rejectActive = null;

export function cancelSpeedTest() {
  activeWorkers.forEach((w) => w.terminate());
  activeWorkers = [];
  rejectActive?.(new TestCancelled("Test cancelled."));
}

function trackWorkers() {
  const NativeWorker = window.Worker;
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      activeWorkers.push(this);
    }
  };
  return () => { window.Worker = NativeWorker; };
}

/**
 * @param {{onPhase:(phase:string, info?:object)=>void, onProgress:(phase:string, mbps:number)=>void}} handlers
 * @returns {Promise<{download_mbps:number, upload_mbps:number, latency_ms:number, jitter_ms:number, server:string|null}>}
 */
export function runSpeedTest({ onPhase, onProgress }) {
  if (!window.ndt7) return Promise.reject(new Error("The speed test couldn't load. Please refresh the page."));
  const restoreWorker = trackWorkers();

  let cancelled = false;
  // After a cancel, late callbacks from the engine are ignored, so the screen and the result stay cancelled.
  const phase = (...args) => { if (!cancelled) onPhase(...args); };
  const progress = (...args) => { if (!cancelled) onProgress(...args); };

  const run = new Promise((resolve, reject) => {
    rejectActive = (error) => { cancelled = true; reject(error); };
    const result = { download_mbps: null, upload_mbps: null, latency_ms: null, jitter_ms: null, server: null };
    let failed = false;
    let lastDownloadTcp = null;
    let lastUploadTcp = null;

    const fail = (detail) => {
      if (failed) return;
      failed = true;
      console.warn("ndt7 error:", detail);
      // "Could not understand response" = M-Lab's server finder didn't return servers (e.g. 429 rate limit).
      const busy = String(detail).includes("Could not understand response");
      reject(new Error(busy
        ? "M-Lab's test servers are busy, or this network has run several tests recently. Please try again in a few minutes."
        : "We couldn't complete the test. Some networks block speed tests. Please try again, or try another network."));
    };

    phase("server");
    window.ndt7.test(
      { userAcceptedDataPolicy: true, metadata: { client_name: "speedspot-mapper" }, ...WORKERS },
      {
        serverChosen: (server) => {
          const place = server?.location ? [server.location.city, server.location.country].filter(Boolean).join(", ") : null;
          result.server = place || server?.machine || null;
          phase("download", { server: result.server });
        },
        downloadMeasurement: (m) => {
          if (m.Source === "client") progress("download", m.Data.MeanClientMbps);
          else if (m.Data?.TCPInfo) lastDownloadTcp = m.Data.TCPInfo;
        },
        downloadComplete: (data) => {
          result.download_mbps = data.LastClientMeasurement?.MeanClientMbps ?? null;
          const tcp = data.LastServerMeasurement?.TCPInfo || lastDownloadTcp;
          if (tcp) {
            result.latency_ms = tcp.MinRTT / 1000;
            result.jitter_ms = tcp.RTTVar / 1000;
          }
          phase("upload");
        },
        uploadMeasurement: (m) => {
          if (m.Source === "server") {
            lastUploadTcp = m.Data?.TCPInfo || lastUploadTcp;
            const mbps = serverUploadMbps(lastUploadTcp);
            if (mbps !== null) progress("upload", mbps);
          } else if (!lastUploadTcp) {
            progress("upload", m.Data.MeanClientMbps);
          }
        },
        uploadComplete: (data) => {
          result.upload_mbps = serverUploadMbps(data.LastServerMeasurement?.TCPInfo || lastUploadTcp)
            ?? data.LastClientMeasurement?.MeanClientMbps ?? null;
        },
        error: fail,
      },
    ).then((exitCode) => {
      if (failed) return;
      const complete = ["download_mbps", "upload_mbps", "latency_ms", "jitter_ms"].every((k) => Number.isFinite(result[k]));
      if (exitCode !== 0 || !complete) fail({ exitCode, result });
      else resolve(result);
    }).catch(fail);
  });
  return run.finally(() => {
    restoreWorker();
    activeWorkers = [];
    rejectActive = null;
  });
}
