/**
 * Mock of the FastAPI backend. Same endpoints and payloads, so switching to the
 * real backend is only a change of NEXT_PUBLIC_API_URL.
 *
 *   GET  /matches            list of matches
 *   POST /match/load         { match_id, mode? }
 *   POST /play | /pause
 *   POST /speed              { factor: 1 | 10 }
 *   POST /seek               { t }   (match second / generator frame)
 *   GET  /state              full MatchState
 *   GET  /stream             SSE: tick | overlay | event | insight | state
 */
import { NextRequest, NextResponse } from 'next/server';
import { mockMatch } from '@/lib/mock/engine';
import { MATCHES } from '@/lib/matches';
import type { Mode, StreamMessage } from '@/lib/contracts';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  const path = (await ctx.params).path.join('/');
  if (path === 'matches') return NextResponse.json(MATCHES);
  if (path === 'state') return NextResponse.json(mockMatch.state());
  if (path === 'health') return NextResponse.json({ status: 'ok' });
  if (path === 'stream') return stream(req);
  return NextResponse.json({ error: `Unknown endpoint: ${path}` }, { status: 404 });
}

export async function POST(req: NextRequest, ctx: Ctx) {
  const path = (await ctx.params).path.join('/');
  const body = await req.json().catch(() => ({}));
  try {
    switch (path) {
      case 'match/load': mockMatch.load(String(body.match_id), (body.mode === 'replay' ? 'replay' : 'live') as Mode); break;
      case 'play': mockMatch.play(); break;
      case 'pause': mockMatch.pause(); break;
      case 'speed': mockMatch.setSpeed(Number(body.factor) === 1 ? 1 : 10); break;
      case 'seek': mockMatch.seek(Number(body.t) || 0); break;
      default: return NextResponse.json({ error: `Unknown endpoint: ${path}` }, { status: 404 });
    }
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 400 });
  }
  return NextResponse.json({ ok: true });
}

function stream(req: NextRequest) {
  const enc = new TextEncoder();
  let cleanup = () => {};
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;
      const write = (s: string) => { if (!closed) { try { controller.enqueue(enc.encode(s)); } catch { closed = true; } } };
      const send = (m: StreamMessage) => write(`event: ${m.type}\ndata: ${JSON.stringify(m.data)}\n\n`);
      write('retry: 3000\n\n');
      send({ type: 'state', data: mockMatch.state() });
      const off = mockMatch.subscribe(send);
      const ping = setInterval(() => write(': ping\n\n'), 15000);
      cleanup = () => { if (closed) return; closed = true; off(); clearInterval(ping); try { controller.close(); } catch { /* already closed */ } };
      req.signal.addEventListener('abort', cleanup);
    },
    cancel() { cleanup(); },
  });
  return new Response(body, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
