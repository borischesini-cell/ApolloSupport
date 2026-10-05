"""Mide el stream real de un device remoto y separa captura de red.

Corre el viewer probe contra el backend y, en la misma ventana, lee los
[SELFTEST] del agente antes y despues. SELFTEST_STATE["frames"] cuenta frames
CAPTURADOS (se incrementa en el loop de captura), mientras que el probe cuenta
frames RECIBIDOS por el viewer. La diferencia dice donde esta el cuello:

  capturados >> recibidos  -> el send_video_loop descarta por hash identico
                              (pantalla quieta) o hay congestion que saltea
  capturados ~= recibidos  -> el loop de captura no da abasto (CPU/fuente)
  ambos bajos y bytes/seg bajo el uplink -> red

El JWT se pasa al probe por variable de entorno y nunca se imprime.

Uso:
  python scripts/measure_remote_stream.py --device 782 --seconds 150
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_selftest as fs  # noqa: E402


def selftest_samples(logs: list[dict], device_id: int) -> list[dict]:
    """Devuelve todos los [SELFTEST] del device, ordenados del mas viejo al mas nuevo."""
    out = []
    for log in logs:
        if log.get("device_id") != device_id:
            continue
        st = fs.parse_selftest(log.get("message") or "")
        if not st:
            continue
        out.append({"ts": str(log.get("timestamp")), "st": st})
    out.reverse()  # el endpoint viene id DESC
    return out


def fmt_sample(row: dict) -> str:
    st = row["st"]
    return (f"  {row['ts'][:19]}  status={st.get('status'):<12} "
            f"frames={st.get('frames'):>5}  age_ms={st.get('frame_age_ms'):>6}  "
            f"viewer={st.get('viewer')} hq={st.get('hq')} rdp={st.get('rdp')} "
            f"met={st.get('method')} cap_err={st.get('cap_err')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, required=True)
    ap.add_argument("--seconds", type=int, default=150)
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()

    base = os.environ.get("APOLLO_BASE_URL", "https://support.ultimate.net.ar").rstrip("/")
    ws_base = os.environ.get("APOLLO_WS_URL", base.replace("https://", "wss://").replace("http://", "ws://"))
    user, pwd = fs.load_credentials()

    token = fs.login(base, user, pwd)
    before = selftest_samples(fs.fetch_logs(base, token, args.limit, args.device), args.device)
    print(f"[ANTES] {len(before)} muestras SELFTEST de device {args.device}")
    for row in before[-3:]:
        print(fmt_sample(row))

    env = dict(os.environ, APOLLO_TOKEN=token)
    cmd = [sys.executable, str(Path(__file__).parent / "viewer_probe_local.py"),
           "--url", ws_base, "--device", str(args.device), "--seconds", str(args.seconds)]
    t0 = datetime.now(timezone.utc)
    print(f"[PROBE] arranca {t0:%H:%M:%S} UTC por {args.seconds}s contra {ws_base}")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(proc.stdout or "")
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    token = fs.login(base, user, pwd)
    after = selftest_samples(fs.fetch_logs(base, token, args.limit, args.device), args.device)
    print(f"[DESPUES] {len(after)} muestras SELFTEST")
    for row in after[-4:]:
        print(fmt_sample(row))

    new = [r for r in after if r not in before]
    if len(new) >= 2:
        first, last = new[0]["st"], new[-1]["st"]
        try:
            t_first = datetime.fromisoformat(new[0]["ts"].replace("Z", "+00:00"))
            t_last = datetime.fromisoformat(new[-1]["ts"].replace("Z", "+00:00"))
            secs = (t_last - t_first).total_seconds()
        except ValueError:
            secs = 0.0
        d_frames = int(last.get("frames", 0)) - int(first.get("frames", 0))
        if secs > 0:
            print(f"[DELTA] {d_frames} frames capturados en {secs:.0f}s "
                  f"-> {d_frames / secs:.2f} FPS de captura")
        else:
            print(f"[DELTA] {d_frames} frames capturados (sin ventana de tiempo util)")
    elif new:
        print(f"[DELTA] solo 1 muestra nueva en la ventana; ampliar --seconds (selftest cada 60s)")
    else:
        print("[DELTA] sin muestras nuevas: el agente no reporto SELFTEST en la ventana")

    print(json.dumps({"device": args.device, "nuevas_muestras": len(new)}, ensure_ascii=False))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
