import { useState } from "react";
import { Download, Bell, Filter } from "lucide-react";
import SignalBadge from "../components/SignalBadge";
import { alertData, SignalType } from "../data/mockData";
import { format } from "date-fns";

export default function Alerts() {
  const [signalFilter, setSignalFilter] = useState<SignalType | 'All'>('All');
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  const filteredAlerts = alertData.filter(alert => 
    signalFilter === 'All' || alert.signal === signalFilter
  );

  const handleExportCSV = () => {
    const headers = ['Time', 'Coin', 'Signal', 'Score'];
    const rows = filteredAlerts.map(alert => [
      format(alert.timestamp, 'yyyy-MM-dd HH:mm:ss'),
      alert.symbol,
      alert.signal,
      alert.score.toString()
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flowscope-alerts-${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold text-foreground mb-2 tracking-tight">Signal History</h1>
          <p className="text-muted-foreground text-lg">Historical detections and notification management</p>
        </div>
        
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-2 px-5 py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-semibold transition-all shadow-lg shadow-primary/30 hover:shadow-primary/40 hover:scale-105"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      {/* Controls */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:border-white/20 transition-all">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-primary" />
              <h3 className="font-semibold text-foreground">Filters</h3>
            </div>
            
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-muted-foreground">Signal:</label>
              <select
                value={signalFilter}
                onChange={(e) => setSignalFilter(e.target.value as SignalType | 'All')}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-foreground font-medium focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
              >
                <option value="All">All Signals</option>
                <option value="Accumulation">Accumulation</option>
                <option value="Breakout">Breakout</option>
                <option value="Short Squeeze">Short Squeeze</option>
                <option value="Long Squeeze">Long Squeeze</option>
                <option value="Watch">Watch</option>
                <option value="Neutral">Neutral</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Bell className="w-4 h-4 text-muted-foreground" />
            <label className="text-sm font-medium text-muted-foreground">Notifications:</label>
            <button
              onClick={() => setNotificationsEnabled(!notificationsEnabled)}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-300 ${
                notificationsEnabled ? 'bg-primary shadow-lg shadow-primary/30' : 'bg-white/10'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform duration-300 shadow-lg ${
                  notificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`text-sm font-semibold ${notificationsEnabled ? 'text-primary' : 'text-muted-foreground'}`}>
              {notificationsEnabled ? 'On' : 'Off'}
            </span>
          </div>
        </div>
      </div>

      {/* Results Count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing <span className="text-foreground font-semibold">{filteredAlerts.length}</span> alerts
        </p>
      </div>

      {/* Alerts Table */}
      <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-white/20 transition-all">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Asset
                </th>
                <th className="text-left px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Signal Type
                </th>
                <th className="text-right px-6 py-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Confidence
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert) => (
                <tr key={alert.id} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-semibold text-foreground">
                        {format(alert.timestamp, 'MMM dd, yyyy')}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {format(alert.timestamp, 'HH:mm:ss')}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <div className="absolute inset-0 bg-primary/20 blur-md rounded-full"></div>
                        <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 border border-white/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                          <span className="text-sm font-bold text-primary">{alert.symbol[0]}</span>
                        </div>
                      </div>
                      <span className="font-semibold text-foreground">{alert.symbol}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <SignalBadge signal={alert.signal} />
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <div className="w-20 h-2 bg-white/5 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-primary to-primary/60 rounded-full transition-all duration-500" 
                          style={{ width: `${alert.score}%` }}
                        ></div>
                      </div>
                      <span className="font-semibold text-foreground w-8">{alert.score}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-white/20 transition-all">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Total Alerts</p>
          <p className="text-3xl font-bold text-foreground">{alertData.length}</p>
        </div>
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-blue-500/20 transition-all">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Accumulation</p>
          <p className="text-3xl font-bold text-blue-400">
            {alertData.filter(a => a.signal === 'Accumulation').length}
          </p>
        </div>
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-emerald-500/20 transition-all">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Breakout</p>
          <p className="text-3xl font-bold text-emerald-400">
            {alertData.filter(a => a.signal === 'Breakout').length}
          </p>
        </div>
        <div className="bg-card/50 backdrop-blur-xl border border-white/10 rounded-2xl p-5 hover:border-primary/20 transition-all">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Avg Score</p>
          <p className="text-3xl font-bold text-primary">
            {Math.round(alertData.reduce((acc, a) => acc + a.score, 0) / alertData.length)}
          </p>
        </div>
      </div>
    </div>
  );
}
