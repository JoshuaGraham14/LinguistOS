// Audio worklet processor: PCM16 encoder.
//
// Runs on the dedicated audio rendering thread (NOT the main thread), so
// encoding and chunking never block React rendering. Receives Float32 mic
// samples from the browser's audio graph at the AudioContext sample rate
// (we configure 24 kHz upstream, matching the `sample_rate=24000` query
// param the backend sends to Deepgram).
//
// Output: posts ArrayBuffers of little-endian PCM16 samples back to the
// main thread via `port.postMessage`. Buffers are transferred (not copied)
// for zero-copy performance. The main thread sends them as raw binary
// frames over the WebSocket to the backend Deepgram proxy — `WebSocket.send`
// isn't available inside an AudioWorkletGlobalScope, so that hop has to
// live on the main thread.
//
// Replaces the deprecated ScriptProcessorNode. ScriptProcessorNode runs
// its callback on the main thread, which is why the browser deprecated
// it: any frame jank stalls audio capture. AudioWorklet runs in a
// separate thread with strict realtime guarantees.

// 1024 samples @ 24 kHz ≈ 42 ms per chunk. Tight enough that audio reaches
// the server with low latency; large enough that we don't flood the
// WebSocket with hundreds of tiny messages per second.
const CHUNK_SAMPLES = 1024;

class PCM16EncoderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(CHUNK_SAMPLES);
    this._index = 0;
  }

  process(inputs) {
    // The Web Audio graph hands us inputs[0][channel][sample]. We're mono
    // (channelCount: 1 on the source), so input[0] is our only channel.
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) {
      // No audio yet — keep the processor alive.
      return true;
    }
    const channel = input[0];

    for (let i = 0; i < channel.length; i++) {
      this._buffer[this._index++] = channel[i];
      if (this._index >= CHUNK_SAMPLES) {
        this._flush();
      }
    }
    return true;
  }

  _flush() {
    // Encode the accumulated Float32 frame as little-endian PCM16.
    const out = new ArrayBuffer(CHUNK_SAMPLES * 2);
    const view = new DataView(out);
    for (let i = 0; i < CHUNK_SAMPLES; i++) {
      // Clamp to [-1, 1] then scale to int16 range.
      const s = Math.max(-1, Math.min(1, this._buffer[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    // Transfer ownership — main thread now owns the buffer, no copy.
    this.port.postMessage(out, [out]);
    this._index = 0;
  }
}

registerProcessor("pcm16-encoder", PCM16EncoderProcessor);
