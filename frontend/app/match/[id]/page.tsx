import { MatchScreen } from '@/components/MatchScreen';

export default async function MatchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ replay?: string }>;
}) {
  const { id } = await params;
  const { replay } = await searchParams;
  return <MatchScreen matchId={id} mode={replay === '1' ? 'replay' : 'live'} />;
}
