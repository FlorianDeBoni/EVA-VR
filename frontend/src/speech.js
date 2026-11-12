// Formats MediaRecorder may support, best first (Safari only does mp4).
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

// How often the microphone level is sampled while recording (milliseconds).
const LEVEL_SAMPLE_MS = 50;

const extensionOf = (mimeType) =>
  mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm";

/**
 * Whether a recording is worth transcribing. Silent or tiny recordings make the speech
 * model invent text, so they must not be sent.
 */
export function hasSpeech({ peak, durationMs }, { minLevel, minMs }) {
  return durationMs >= minMs && peak >= minLevel;
}

/**
 * Records the microphone: `await start()`, then `await stop()` ->
 * { blob, filename, durationMs, peak } where peak is the loudest level heard (0..1).
 */
export class Recorder {
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.peak = 0;
    this.#watchLevel();

    const mimeType = MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    this.startedAt = performance.now();
    this.recorder.start();
  }

  stop() {
    return new Promise((resolve) => {
      this.recorder.onstop = () => {
        const durationMs = performance.now() - this.startedAt;
        clearInterval(this.levelTimer);
        this.audioContext.close();
        this.stream.getTracks().forEach((track) => track.stop());
        const type = this.recorder.mimeType || "audio/webm";
        resolve({
          blob: new Blob(this.chunks, { type }),
          filename: `recording.${extensionOf(type)}`,
          durationMs,
          peak: this.peak,
        });
      };
      this.recorder.stop();
    });
  }

  // Tracks the loudest moment (RMS of short frames) while recording.
  #watchLevel() {
    this.audioContext = new AudioContext();
    const analyser = this.audioContext.createAnalyser();
    this.audioContext.createMediaStreamSource(this.stream).connect(analyser);
    const frame = new Float32Array(analyser.fftSize);
    this.levelTimer = setInterval(() => {
      analyser.getFloatTimeDomainData(frame);
      const rms = Math.sqrt(frame.reduce((sum, v) => sum + v * v, 0) / frame.length);
      this.peak = Math.max(this.peak, rms);
    }, LEVEL_SAMPLE_MS);
  }
}
