'use client';

import { useCallback, useEffect, useReducer, useRef } from 'react';
import type {
  Insight, Marker, MatchEvent, MatchState, Mode, Overlay, OverlaySlot, Speed, Tick,
} from './contracts';

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || '/api/mock').replace(/\/$/, '');

/** How long a fast-lane overlay stays on screen (real time). */
const OVERLAY_MS = 4000;

export type ActiveOverlay = Overlay & { shownAt: number };
export type Connection = 'connecting' | 'live' | 'reconnecting';

export type StreamState = {
  tick: Tick | null;
  mode: Mode;
  events: MatchEvent[];
  insights: Insight[];
  overlays: Partial<Record<OverlaySlot, ActiveOverlay>>;
  markers?: Marker[];
  /** Last frame of the match and first frame of the second half */
  duration: number;
  halftime: number;
  connection: Connection;
  /** Real time at which the latest tick arrived (for interpolation) */
  tickAt: number;
  error: string | null;
};

type Action =
  | { type: 'state'; data: MatchState }
  | { type: 'tick'; data: Tick }
  | { type: 'overlay'; data: Overlay }
  | { type: 'expire'; slot: OverlaySlot; id: string }
  | { type: 'event'; data: MatchEvent }
  | { type: 'insight'; data: Insight }
  | { type: 'connection'; value: Connection }
  | { type: 'error'; value: string | null };

const initial: StreamState = {
  tick: null, mode: 'live', events: [], insights: [], overlays: {}, duration: 5400, halftime: 2700, connection: 'connecting', tickAt: 0, error: null,
};

function reducer(s: StreamState, a: Action): StreamState {
  const gen = s.tick?.generation ?? 0;
  switch (a.type) {
    case 'state':
      return {
        ...s,
        tick: a.data,
        tickAt: performance.now(),
        mode: a.data.mode,
        events: a.data.events,
        insights: a.data.insights,
        markers: a.data.markers,
        duration: a.data.duration,
        halftime: a.data.halftime,
        overlays: {},
      };
    case 'tick': {
      // A new generation means a seek happened: clear what belongs to the old one.
      const newGen = a.data.generation !== gen;
      return {
        ...s,
        tick: a.data,
        tickAt: performance.now(),
        overlays: newGen ? {} : s.overlays,
        events: newGen ? s.events.filter((e) => e.t <= a.data.t) : s.events,
      };
    }
    case 'overlay':
      if (a.data.generation < gen) return s;
      return { ...s, overlays: { ...s.overlays, [a.data.slot]: { ...a.data, shownAt: performance.now() } } };
    case 'expire':
      if (s.overlays[a.slot]?.id !== a.id) return s;
      return { ...s, overlays: { ...s.overlays, [a.slot]: undefined } };
    case 'event':
      if (s.events.some((e) => e.id === a.data.id)) return s;
      return { ...s, events: [...s.events, a.data].sort((x, y) => x.t - y.t) };
    case 'insight': {
      if (a.data.generation < gen) return s;
      const i = s.insights.findIndex((x) => x.id === a.data.id);
      const insights = i === -1 ? [...s.insights, a.data] : s.insights.map((x, j) => (j === i ? a.data : x));
      return { ...s, insights };
    }
    case 'connection':
      return { ...s, connection: a.value };
    case 'error':
      return { ...s, error: a.value };
  }
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
}

/**
 * The only place the frontend talks to the backend.
 * Works against the mock (/api/mock) and the real FastAPI backend alike.
 */
export function useMatchStream(matchId: string, mode: Mode) {
  const [state, dispatch] = useReducer(reducer, initial);
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());

  useEffect(() => {
    let es: EventSource | null = null;
    let cancelled = false;
    const resync = async () => {
      try {
        const res = await fetch(`${API_URL}/state`, { cache: 'no-store' });
        if (res.ok && !cancelled) dispatch({ type: 'state', data: await res.json() });
      } catch { /* the stream will send state too */ }
    };

    (async () => {
      try {
        await post('/match/load', { match_id: matchId, mode });
      } catch (e) {
        dispatch({ type: 'error', value: `Could not load the match. Is the backend running at ${API_URL}?` });
      }
      if (cancelled) return;
      es = new EventSource(`${API_URL}/stream`);
      es.onopen = () => { dispatch({ type: 'connection', value: 'live' }); dispatch({ type: 'error', value: null }); resync(); };
      es.onerror = () => dispatch({ type: 'connection', value: 'reconnecting' });
      const on = <T,>(name: string, fn: (d: T) => void) =>
        es!.addEventListener(name, (ev) => fn(JSON.parse((ev as MessageEvent).data)));
      on<MatchState>('state', (d) => dispatch({ type: 'state', data: d }));
      on<Tick>('tick', (d) => dispatch({ type: 'tick', data: d }));
      on<MatchEvent>('event', (d) => dispatch({ type: 'event', data: d }));
      on<Insight>('insight', (d) => dispatch({ type: 'insight', data: d }));
      on<Overlay>('overlay', (d) => {
        dispatch({ type: 'overlay', data: d });
        const h = setTimeout(() => { timers.current.delete(h); dispatch({ type: 'expire', slot: d.slot, id: d.id }); }, OVERLAY_MS);
        timers.current.add(h);
      });
    })();

    const pending = timers.current;
    return () => {
      cancelled = true;
      es?.close();
      for (const h of pending) clearTimeout(h);
      pending.clear();
    };
  }, [matchId, mode]);

  const act = useCallback((path: string, body?: unknown) => {
    post(path, body).catch((e) => dispatch({ type: 'error', value: (e as Error).message }));
  }, []);

  return {
    ...state,
    play: useCallback(() => act('/play'), [act]),
    pause: useCallback(() => act('/pause'), [act]),
    setSpeed: useCallback((s: Speed) => act('/speed', { factor: s }), [act]),
    seek: useCallback((t: number) => act('/seek', { t }), [act]),
  };
}
