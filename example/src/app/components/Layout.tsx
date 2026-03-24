import { Outlet, Link, useLocation } from "react-router";
import { Search, Bell, User, Zap } from "lucide-react";

export default function Layout() {
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Modern Top Navigation with backdrop blur */}
      <nav className="sticky top-0 z-50 bg-card/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-[1600px] mx-auto px-8 py-5">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="relative">
                <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full"></div>
                <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-white" fill="currentColor" />
                </div>
              </div>
              <div>
                <span className="text-xl font-semibold tracking-tight text-foreground">FlowScope</span>
                <p className="text-[10px] text-muted-foreground -mt-0.5">Pro Analytics</p>
              </div>
            </Link>
            
            {/* Navigation Links */}
            <div className="flex items-center gap-2">
              <Link
                to="/"
                className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive('/') && location.pathname === '/'
                    ? 'bg-primary/10 text-primary shadow-lg shadow-primary/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/scanner"
                className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive('/scanner')
                    ? 'bg-primary/10 text-primary shadow-lg shadow-primary/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                Scanner
              </Link>
              <Link
                to="/alerts"
                className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive('/alerts')
                    ? 'bg-primary/10 text-primary shadow-lg shadow-primary/20'
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                Alerts
              </Link>
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search assets..."
                  className="pl-11 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 w-64 transition-all"
                />
              </div>
              
              <button className="p-2.5 hover:bg-white/5 rounded-xl transition-all relative group">
                <Bell className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
                <span className="absolute top-2 right-2 w-2 h-2 bg-primary rounded-full animate-pulse"></span>
              </button>
              
              <button className="p-2.5 hover:bg-white/5 rounded-xl transition-all group">
                <User className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-[1600px] mx-auto px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
