import CoinDetailPage from "@/app/pages/coin/CoinDetailPage";

export default async function CoinRoute({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  return <CoinDetailPage symbol={symbol} />;
}
