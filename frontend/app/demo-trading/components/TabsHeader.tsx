"use client";

type DemoTab = "positions" | "open" | "orders" | "trades" | "assets";

interface TabsHeaderProps {
  activeTab: DemoTab;
  onTabChange: (tab: DemoTab) => void;
  counts?: {
    positions?: number;
    openOrders?: number;
    orderHistory?: number;
    tradeHistory?: number;
  };
}

export default function TabsHeader({
  activeTab,
  onTabChange,
  counts,
}: TabsHeaderProps) {
  const tabs: { id: DemoTab; label: string; count?: number }[] = [
    {
      id: "positions",
      label: "Positions",
      count: counts?.positions,
    },
    {
      id: "open",
      label: "Open Orders",
      count: counts?.openOrders,
    },
    { id: "orders", label: "Order History", count: counts?.orderHistory },
    { id: "trades", label: "Trade History", count: counts?.tradeHistory },
    { id: "assets", label: "Assets" },
  ];

  return (
    <div className="mb-4 border-b border-white/10">
      <div className="flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`relative px-4 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab.id
                ? "text-yellow-400"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span
                className={`ml-0.5 ${
                  activeTab === tab.id ? "text-yellow-400" : "text-slate-500"
                }`}
              >
                ({tab.count})
              </span>
            )}
            {/* Active indicator bar */}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-yellow-400 rounded-t" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
