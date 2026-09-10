/**
 * H.264 Annex-B → WebCodecs VideoDecoder → canvas (sin MSE/JMuxer).
 */

export function isWebCodecsH264Supported(): boolean {
  return typeof VideoDecoder !== 'undefined' && typeof EncodedVideoChunk !== 'undefined';
}

function removeStartCode(nal: Uint8Array): Uint8Array {
  if (nal.length >= 4 && nal[0] === 0 && nal[1] === 0 && nal[2] === 0 && nal[3] === 1) {
    return nal.subarray(4);
  }
  if (nal.length >= 3 && nal[0] === 0 && nal[1] === 0 && nal[2] === 1) {
    return nal.subarray(3);
  }
  return nal;
}

function nalType(nal: Uint8Array): number {
  const raw = removeStartCode(nal);
  return raw.length > 0 ? raw[0] & 0x1f : -1;
}

function splitAnnexBNals(data: Uint8Array): { nals: Uint8Array[]; remainder: Uint8Array } {
  const starts: number[] = [];
  for (let i = 0; i <= data.length - 3; i++) {
    if (data[i] === 0 && data[i + 1] === 0) {
      if (data[i + 2] === 1) starts.push(i);
      else if (data[i + 2] === 0 && i + 3 < data.length && data[i + 3] === 1) starts.push(i);
    }
  }
  if (starts.length === 0) return { nals: [], remainder: data };

  const nals: Uint8Array[] = [];
  for (let i = 0; i < starts.length - 1; i++) {
    nals.push(data.subarray(starts[i], starts[i + 1]));
  }
  const remainder = data.subarray(starts[starts.length - 1]);
  return { nals, remainder };
}

function buildAvcConfigDescription(sps: Uint8Array, pps: Uint8Array): Uint8Array {
  const spsRaw = removeStartCode(sps);
  const ppsRaw = removeStartCode(pps);
  const out = new Uint8Array(11 + spsRaw.length + ppsRaw.length);
  let o = 0;
  out[o++] = 1;
  out[o++] = spsRaw[1];
  out[o++] = spsRaw[2];
  out[o++] = spsRaw[3];
  out[o++] = 0xff;
  out[o++] = 0xe1;
  out[o++] = (spsRaw.length >> 8) & 0xff;
  out[o++] = spsRaw.length & 0xff;
  out.set(spsRaw, o);
  o += spsRaw.length;
  out[o++] = 1;
  out[o++] = (ppsRaw.length >> 8) & 0xff;
  out[o++] = ppsRaw.length & 0xff;
  out.set(ppsRaw, o);
  return out;
}

function codecStringFromSps(sps: Uint8Array): string {
  const raw = removeStartCode(sps);
  const hex = (n: number) => n.toString(16).padStart(2, '0').toUpperCase();
  return `avc1.${hex(raw[1])}${hex(raw[2])}${hex(raw[3])}`;
}

function annexBToAvcc(nal: Uint8Array): Uint8Array {
  const raw = removeStartCode(nal);
  const out = new Uint8Array(4 + raw.length);
  out[0] = (raw.length >> 24) & 0xff;
  out[1] = (raw.length >> 16) & 0xff;
  out[2] = (raw.length >> 8) & 0xff;
  out[3] = raw.length & 0xff;
  out.set(raw, 4);
  return out;
}

function concatAvcc(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, p) => sum + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

export class H264WebCodecsPlayer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D | null = null;
  private decoder: VideoDecoder | null = null;
  private buffer = new Uint8Array(0);
  private sps: Uint8Array | null = null;
  private pps: Uint8Array | null = null;
  private configured = false;
  private gotKeyframe = false;
  private timestampUs = 0;
  private frameDurUs: number;
  private pendingVcl: Uint8Array[] = [];
  private pendingIsKeyframe = false;
  private onError?: (msg: string) => void;
  private drawPending = false;
  private closed = false;

  constructor(canvas: HTMLCanvasElement, fps = 24, onError?: (msg: string) => void) {
    this.canvas = canvas;
    this.frameDurUs = Math.round(1_000_000 / fps);
    this.onError = onError;
    this.ctx = canvas.getContext('2d', { alpha: false });
  }

  feed(chunk: ArrayBuffer): void {
    if (this.closed) return;
    const incoming = new Uint8Array(chunk);
    if (this.buffer.length === 0) {
      this.buffer = incoming;
    } else {
      const combined = new Uint8Array(this.buffer.length + incoming.length);
      combined.set(this.buffer);
      combined.set(incoming, this.buffer.length);
      this.buffer = combined;
    }
    this.processBuffer();
  }

  private processBuffer(): void {
    const { nals, remainder } = splitAnnexBNals(this.buffer);
    this.buffer = remainder.length > 0 ? remainder.slice() : new Uint8Array(0);

    for (const nal of nals) {
      const t = nalType(nal);
      if (t === 7) {
        this.sps = nal;
        this.tryConfigure();
        continue;
      }
      if (t === 8) {
        this.pps = nal;
        this.tryConfigure();
        continue;
      }
      if (t === 6) continue;

      if (t === 9) {
        this.flushPendingAccessUnit();
        continue;
      }

      if (t === 5 || t === 1) {
        if (this.pendingVcl.length > 0) {
          this.flushPendingAccessUnit();
        }
        this.pendingVcl = [nal];
        this.pendingIsKeyframe = t === 5;
        if (t === 5) {
          this.flushPendingAccessUnit();
        } else {
          // ffmpeg ultrafast: 1 slice = 1 frame → flush each P-slice
          this.flushPendingAccessUnit();
        }
        continue;
      }

      if (this.pendingVcl.length > 0 && t !== 9) {
        this.pendingVcl.push(nal);
      }
    }
  }

  private flushPendingAccessUnit(): void {
    if (this.pendingVcl.length === 0) return;
    const isKeyframe = this.pendingIsKeyframe || nalType(this.pendingVcl[0]) === 5;
    const vcls = this.pendingVcl;
    this.pendingVcl = [];
    this.pendingIsKeyframe = false;
    this.flushAccessUnit(isKeyframe, vcls);
  }

  private flushAccessUnit(isKeyframe: boolean, vcls: Uint8Array[]): void {
    if (this.closed || !this.configured || vcls.length === 0) return;
    if (!isKeyframe && !this.gotKeyframe) return;
    const dec = this.decoder;
    if (!dec || dec.state === 'closed') return;

    const avccParts = vcls.map(annexBToAvcc);
    const data = concatAvcc(avccParts);

    try {
      const chunk = new EncodedVideoChunk({
        type: isKeyframe ? 'key' : 'delta',
        timestamp: this.timestampUs,
        data,
      });
      this.timestampUs += this.frameDurUs;
      if (isKeyframe) this.gotKeyframe = true;
      dec.decode(chunk);
    } catch (e) {
      const msg = String(e);
      if (msg.includes('closed codec') || msg.includes('InvalidStateError')) {
        this.reset();
        return;
      }
      this.onError?.(`decode: ${e}`);
    }
  }

  private tryConfigure(): void {
    if (this.configured || !this.sps || !this.pps) return;

    try {
      const description = buildAvcConfigDescription(this.sps, this.pps);
      const codec = codecStringFromSps(this.sps);

      if (this.decoder) {
        try {
          this.decoder.close();
        } catch {
          /* */
        }
      }

      this.decoder = new VideoDecoder({
        output: (frame) => {
          if (this.drawPending) {
            frame.close();
            return;
          }
          this.drawPending = true;
          requestAnimationFrame(() => {
            this.drawPending = false;
            const ctx = this.ctx;
            if (!ctx) {
              frame.close();
              return;
            }
            const w = frame.displayWidth;
            const h = frame.displayHeight;
            if (this.canvas.width !== w || this.canvas.height !== h) {
              this.canvas.width = w;
              this.canvas.height = h;
            }
            ctx.drawImage(frame, 0, 0, w, h);
            frame.close();
          });
        },
        error: (e) => {
          this.gotKeyframe = false;
          this.onError?.(String(e));
          try {
            this.decoder?.reset();
          } catch {
            /* */
          }
        },
      });

      this.decoder.configure({
        codec,
        description,
        optimizeForLatency: true,
        hardwareAcceleration: 'prefer-hardware',
      });
      this.configured = true;
      this.gotKeyframe = false;
      this.timestampUs = 0;
    } catch (e) {
      this.onError?.(`configure: ${e}`);
    }
  }

  reset(): void {
    this.buffer = new Uint8Array(0);
    this.sps = null;
    this.pps = null;
    this.pendingVcl = [];
    this.pendingIsKeyframe = false;
    this.configured = false;
    this.gotKeyframe = false;
    this.timestampUs = 0;
    if (this.decoder) {
      try {
        this.decoder.reset();
      } catch {
        /* */
      }
    }
  }

  destroy(): void {
    this.closed = true;
    this.reset();
    if (this.decoder) {
      try {
        this.decoder.close();
      } catch {
        /* */
      }
      this.decoder = null;
    }
    this.ctx = null;
  }
}
