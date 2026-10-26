'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Marker, Mode } from '@/lib/contracts';
import { markersFrom } from '@/lib/markers';
import { useMatchStream } from '@/lib/useMatchStream';
import { useInterpolatedFrame } from '@/lib/useInterpolatedFrame';
import { Scorebar } from './Scorebar';
import { BallMarker, PitchSurface, PlayerChips } from './Pitch';
import { OverlayLayer } from './OverlayLayer';
import { ProducerFeed } from './ProducerFeed';
import { KeyMoment } from './KeyMoment';
import { Controls } from './Controls';
import { FactCheck, Whistle } from './icons';
import { TeamsProvider, teamColorVars, teamsFor } from '@/lib/teams';

const PERIOD: Record<number, string> = { 1: '1ST HALF', 2: '2ND HALF', 3: 'EXTRA TIME 1', 4: 'EXTRA TIME 2', 5: 'PENALTIES' };


// The pitch keeps its 111:74 ratio and leaves at least 400 px for the feed.
const PITCH_WIDTH = 'min(1248px, calc(100vw - 80px - 32px - 400px), calc((100vh - 104px - 112px - 32px) * 1.5))';

export function MatchScreen({ matchId, mode }: { matchId: string; mode: Mode }) {
  const s = useMatchStream(matchId, mode);
  const teams = useMemo(() => teamsFor(matchId), [matchId]);
  const [feedMode, setFeedMode] = useState<'casual' | 'analyst'>('casual');
  const [focusId, setFocusId] = useState<string | null>(null);

  const tick = s.tick;
  const frame = tick?.frame ?? null;
  const positions = useInterpolatedFrame(frame, tick?.speed ?? 10, tick?.playing ?? false);

  // Key moment: shown while the backend says so, then the hero card moves to the feed.
  const keyId = tick?.keyMomentId ?? null;
  const [shownKeyId, setShownKeyId] = useState<string | null>(null);
  const [exiting, setExiting] = useState(false);
  const [arrivingId, setArrivingId] = useState<string | null>(null);
  const exitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (keyId) {
      if (exitTimer.current) clearTimeout(exitTimer.current);
      setExiting(false);
      setShownKeyId(keyId);
    } else if (shownKeyId) {
      setExiting(true);
      const heroInsight = s.insights.find((i) => i.momentId === shownKeyId);
      exitTimer.current = setTimeout(() => {
        setShownKeyId(null);
        setExiting(false);
        setArrivingId(heroInsight?.id ?? null);
      }, 480);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyId]);

  const keyEvent = shownKeyId ? s.events.find((e) => e.id === shownKeyId) : undefined;
  const heroInsight = shownKeyId ? s.insights.find((i) => i.momentId === shownKeyId) : undefined;
  const feedInsights = s.insights.filter((i) => i.id !== heroInsight?.id);

  const t = tick?.t ?? 0;
  const markers: Marker[] = useMemo(
    () => s.markers ?? markersFrom(s.events, s.insights.filter((i) => i.phase === 'done' && i.type !== 'tactics')),
    [s.markers, s.events, s.insights],
  );
  const period = !tick ? '' : tick.finished ? 'FULL TIME' : PERIOD[tick.period] ?? '';

  // Tactics cards only show in Analyst mode, so their corrections only get the pill there.
  const recentCorrection = s.insights.find((i) => i.status === 'corrected' && i.phase === 'done' && t - i.t < 240 && t >= i.t
    && (i.type !== 'tactics' || feedMode === 'analyst'));
  const overlays = Object.values(s.overlays).filter((o): o is NonNullable<typeof o> => !!o);
  const stats = tick?.stats ?? { score: [0, 0] as [number, number], xg: [0, 0] as [number, number], possession: [50, 50] as [number, number] };

  return (
    <TeamsProvider teams={teams}>
    <div className="flex h-screen min-h-[720px] flex-col overflow-hidden bg-bg text-fg" style={teamColorVars(teams) as React.CSSProperties}>
      <Scorebar stats={stats} clock={tick?.clock ?? '00:00'} period={period} mode={s.mode} events={s.events} />

      <main className="flex min-h-0 flex-1 gap-8 px-10 py-4">
        <div
          className="relative flex-none self-start overflow-hidden rounded-lg shadow-[0_12px_32px_rgba(0,0,0,.35)]"
          style={{ width: PITCH_WIDTH, aspectRatio: '111 / 74' }}
          aria-label="Pitch"
        >
          <PitchSurface />
          {frame && positions && (
            <>
              <OverlayLayer layer="lines" overlays={overlays} players={frame.players} positions={positions.players} events={s.events} />
              <PlayerChips players={frame.players} positions={positions.players} />
              <BallMarker at={positions.ball} />
              <OverlayLayer layer="labels" overlays={overlays} players={frame.players} positions={positions.players} events={s.events} />
            </>
          )}

          {keyEvent && <KeyMoment event={keyEvent} insight={heroInsight} stats={stats} mode={feedMode} exiting={exiting} />}

          {!keyEvent && recentCorrection && (
            <button
              type="button"
              onClick={() => setFocusId(recentCorrection.id + ':' + Date.now())}
              className="itg-in absolute right-7 top-7 flex items-center gap-[10px] whitespace-nowrap rounded-full border border-corrected bg-[rgba(12,14,13,.9)] py-[10px] pl-3 pr-4 text-[15px] font-semibold text-chalk"
            >
              <FactCheck size={18} color="var(--itg-bad)" />
              Fact-check · 1 claim corrected
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
          )}

          {!keyEvent && tick?.finished && (
            <div className="itg-in absolute left-7 top-7 flex items-center gap-2 rounded-full bg-[rgba(12,14,13,.88)] py-2 pl-[10px] pr-[14px] text-[15px] font-semibold text-chalk">
              <Whistle size={18} />
              Full time · Kingsbridge {stats.score[0]}-{stats.score[1]} Northgate
            </div>
          )}

          {(s.connection === 'reconnecting' || s.error) && (
            <div className="itg-in absolute bottom-7 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full bg-[rgba(12,14,13,.9)] py-[10px] pl-[14px] pr-[18px] text-[15px] text-chalk shadow-[0_12px_32px_rgba(0,0,0,.35)]" role="status">
              <span className="itg-spin inline-block h-4 w-4 rounded-full border-2 border-white/25 border-t-chalk" />
              <span className="font-semibold">{s.error ?? 'Stream dropped. Reconnecting…'}</span>
              {!s.error && <span className="font-mono text-[12px] text-[#B8B4AD]">Retry in 3 s</span>}
            </div>
          )}

          {!tick && !s.error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="rounded-full bg-[rgba(12,14,13,.88)] px-4 py-2 font-mono text-[13px] tracking-[.12em] text-chalk">LOADING MATCH…</div>
            </div>
          )}
        </div>

        <ProducerFeed
          insights={feedInsights}
          mode={feedMode}
          onMode={setFeedMode}
          arrivingId={arrivingId}
          focusId={focusId}
          scouting={s.scouting}
        />
      </main>

      <Controls
        t={t}
        minute={tick?.minute ?? '1'}
        duration={s.duration}
        halftime={s.halftime}
        speed={tick?.speed ?? 10}
        playing={tick?.playing ?? false}
        keyMoment={!!keyId}
        finished={!!tick?.finished}
        markers={s.mode === 'replay' ? markers : markers.filter((m) => m.t <= t)}
        onToggle={() => (tick?.playing ? s.pause() : s.play())}
        onSpeed={s.setSpeed}
        onSeek={s.seek}
      />
    </div>
    </TeamsProvider>
  );
}
