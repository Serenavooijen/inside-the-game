'use client';

import { useEffect, useRef, useState } from 'react';
import type { Frame, Point } from './contracts';

type Positions = { players: Record<string, Point>; ball: Point };

const toPositions = (f: Frame): Positions => ({
  players: Object.fromEntries(f.players.map((p) => [p.id, { x: p.x, y: p.y }])),
  ball: { ...f.ball },
});

/**
 * The backend sends one frame per match second. This hook moves players and the
 * ball smoothly from where they are drawn now to the newest frame, over the real
 * time that one match second takes at the current speed.
 */
export function useInterpolatedFrame(frame: Frame | null, speed: number, playing: boolean): Positions | null {
  const [pos, setPos] = useState<Positions | null>(frame ? toPositions(frame) : null);
  const drawn = useRef<Positions | null>(pos);
  const anim = useRef<{ from: Positions; to: Positions; start: number; dur: number } | null>(null);
  const lastT = useRef<number | null>(null);

  useEffect(() => {
    if (!frame) return;
    const target = toPositions(frame);
    const jump = lastT.current === null || Math.abs(frame.t - lastT.current) > 3;
    lastT.current = frame.t;
    if (jump || !drawn.current || !playing) {
      anim.current = null;
      drawn.current = target;
      setPos(target);
      return;
    }
    // Players coming on as substitutes have no "from": they appear where they are.
    const from: Positions = {
      ball: drawn.current.ball,
      players: Object.fromEntries(Object.keys(target.players).map((id) => [id, drawn.current!.players[id] ?? target.players[id]])),
    };
    anim.current = { from, to: target, start: performance.now(), dur: 1000 / Math.max(1, speed) };
  }, [frame, speed, playing]);

  useEffect(() => {
    let raf = 0;
    const lerp = (a: Point, b: Point, k: number) => ({ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k });
    const loop = (now: number) => {
      const a = anim.current;
      if (a) {
        const k = Math.min(1, (now - a.start) / a.dur);
        const next: Positions = {
          ball: lerp(a.from.ball, a.to.ball, k),
          players: Object.fromEntries(Object.keys(a.to.players).map((id) => [id, lerp(a.from.players[id], a.to.players[id], k)])),
        };
        drawn.current = next;
        setPos(next);
        if (k >= 1) anim.current = null;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return pos;
}
