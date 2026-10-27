import { useLayoutEffect, useRef } from 'react';
import type { MatchEvent, Player, Point } from '@/lib/contracts';
import type { ActiveOverlay } from '@/lib/useMatchStream';
import { useTeams } from '@/lib/teams';
import { NameTag, pct } from './Pitch';

type Props = {
  overlays: ActiveOverlay[];
  players: Player[];
  positions: Record<string, Point>;
  events: MatchEvent[];
  /** 'lines' goes under the player chips, 'labels' on top */
  layer: 'lines' | 'labels';
};


const badge = 'absolute flex items-center whitespace-nowrap rounded-md border border-white/[.12] bg-[rgba(12,14,13,.88)] px-[14px] py-2 text-chalk itg-in';
const labelCls = 'font-mono text-label tracking-[.12em] text-[#B8B4AD]';
const bigNum = 'font-display text-[28px] font-extrabold leading-none';

// Which label stays put when two touch: the name tag, then shot, pass, sprint (data-label = priority).
const PRIORITY = { tag: 0, shot: 1, pass: 2, sprint: 3 } as const;
const GAP = 6;

const overlaps = (a: DOMRect, b: DOMRect) =>
  a.left < b.right + GAP && b.left < a.right + GAP && a.top < b.bottom + GAP && b.top < a.bottom + GAP;

/** Labels that touch move apart vertically (up first, down when there is no room above), measured in the DOM,
 *  so it holds at every screen size. Runs after every render, because the players keep moving. */
function useSeparatedLabels(box: React.RefObject<HTMLDivElement | null>, active: boolean) {
  useLayoutEffect(() => {
    if (!active || !box.current) return;
    const bounds = box.current.getBoundingClientRect();
    const els = [...box.current.querySelectorAll<HTMLElement>('[data-label]')];
    els.forEach((e) => { e.style.marginTop = '0px'; });
    els.sort((a, b) => Number(a.dataset.label) - Number(b.dataset.label));
    const placed: DOMRect[] = [];
    for (const e of els) {
      let r = e.getBoundingClientRect();
      const step = r.height + GAP;
      for (const k of [-1, 1, -2, 2, -3, 3]) {
        if (!placed.some((p) => overlaps(p, r))) break;
        const top = r.top + k * step - Number.parseFloat(e.style.marginTop || '0');
        if (top < bounds.top || top + r.height > bounds.bottom) continue;
        e.style.marginTop = `${k * step}px`;
        r = e.getBoundingClientRect();
      }
      placed.push(r);
    }
  });
}

/** Fast lane: white TV graphics on the pitch. No accent colour here. */
export function OverlayLayer({ overlays, players, positions, events, layer }: Props) {
  const teams = useTeams();
  const byId = Object.fromEntries(players.map((p) => [p.id, p]));
  const booked = new Set(events.filter((e) => e.kind === 'yellow' && e.playerId).map((e) => e.playerId!));
  const at = (id: string): Point | undefined => positions[id] ?? byId[id];

  const lines: React.ReactNode[] = [];
  const html: React.ReactNode[] = [];
  const box = useRef<HTMLDivElement>(null);
  useSeparatedLabels(box, layer === 'labels');

  for (const o of overlays) {
    const p = byId[o.playerId];
    const pos = at(o.playerId);
    if (!p || !pos) continue;

    if (o.slot === 'tag') {
      const flip = pos.x > 86;
      html.push(
        <div
          key={o.id}
          data-label={PRIORITY.tag}
          className="itg-in absolute"
          style={{ left: `calc(${pct(pos).left} ${flip ? '-' : '+'} 26px)`, top: pct(pos).top, transform: `translate(${flip ? '-100%' : '0'}, -50%)` }}
        >
          <NameTag player={p} booked={booked.has(p.id)} />
        </div>,
      );
    }

    if (o.slot === 'pass' && o.to) {
      const ang = Math.atan2(o.to.y - pos.y, o.to.x - pos.x);
      const ah = (d: number) => `${o.to!.x - Math.cos(ang + d) * 1.6},${o.to!.y - Math.sin(ang + d) * 1.6}`;
      lines.push(
        <g key={o.id} className="itg-in">
          <line x1={pos.x} y1={pos.y} x2={o.to.x} y2={o.to.y} stroke="#fff" strokeWidth=".35" strokeDasharray="1 .7" strokeLinecap="round" />
          <path d={`M${ah(0.5)} L${o.to.x},${o.to.y} L${ah(-0.5)}`} fill="none" stroke="#fff" strokeWidth=".35" strokeLinecap="round" strokeLinejoin="round" />
        </g>,
      );
      const mid = { x: (pos.x + o.to.x) / 2, y: (pos.y + o.to.y) / 2 };
      const q = o.value ?? 0;
      html.push(
        <div key={`${o.id}-b`} data-label={PRIORITY.pass} className={`${badge} gap-3`} style={{ ...pct(mid), transform: 'translate(-50%, calc(-50% - 44px))' }}>
          <div className="flex flex-col gap-[2px]">
            <div className={labelCls}>PASS QUALITY</div>
            <div className="h-1 w-[84px] rounded-full bg-white/15"><div className="h-full rounded-full bg-chalk" style={{ width: `${Math.round(q * 100)}%` }} /></div>
          </div>
          <div className={bigNum}>{q.toFixed(2)}</div>
        </div>,
      );
    }

    if (o.slot === 'shot' && o.to) {
      lines.push(
        <line key={o.id} className="itg-in" x1={pos.x} y1={pos.y} x2={o.to.x} y2={o.to.y} stroke="#fff" strokeWidth=".4" strokeDasharray="1 .6" strokeLinecap="round" />,
      );
      html.push(
        <div key={`${o.id}-b`} data-label={PRIORITY.shot} className={`${badge} gap-[10px]`} style={{ ...pct(pos), transform: 'translate(-50%, calc(-50% - 64px))' }}>
          <div className={labelCls}>SHOT · xG</div>
          <div className={bigNum}>{(o.value ?? 0).toFixed(2)}</div>
        </div>,
      );
    }

    if (o.slot === 'sprint' && o.from) {
      const gid = `sprint-${o.id}`;
      lines.push(
        <g key={o.id} className="itg-in">
          <defs>
            <linearGradient id={gid} gradientUnits="userSpaceOnUse" x1={o.from.x} y1={o.from.y} x2={pos.x} y2={pos.y}>
              <stop offset="0" style={{ stopColor: teams.text(p.team) }} stopOpacity="0" />
              <stop offset="1" style={{ stopColor: teams.text(p.team) }} stopOpacity=".9" />
            </linearGradient>
          </defs>
          <line x1={o.from.x} y1={o.from.y} x2={pos.x} y2={pos.y} stroke={`url(#${gid})`} strokeWidth="1.6" strokeLinecap="round" />
        </g>,
      );
      const mid = { x: (pos.x + o.from.x) / 2, y: (pos.y + o.from.y) / 2 };
      html.push(
        <div key={`${o.id}-b`} data-label={PRIORITY.sprint} className={`${badge} gap-[10px]`} style={{ ...pct(mid), transform: 'translate(-50%, calc(-50% - 52px))' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ stroke: teams.text(p.team) }} strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M13 4 21 12 13 20M3 8h7M5 12h8M3 16h7" /></svg>
          <div className={labelCls}>SPRINT · {p.n}</div>
          <div className={bigNum}>{(o.value ?? 0).toFixed(1)}<span className="text-[16px] font-bold text-[#B8B4AD]"> km/h</span></div>
        </div>,
      );
    }
  }

  if (layer === 'lines') {
    return <svg viewBox="-3 -3 111 74" className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>{lines}</svg>;
  }
  // Rendered after the player chips (see MatchScreen), so name tags and badges lie above them; no z-index,
  // so the key-moment layer that follows still covers them.
  return <div ref={box} className="pointer-events-none absolute inset-0">{html}</div>;
}
