import { Link, useLocation } from 'react-router';
import { Search, Bell, User, Activity } from 'lucide-react';
import { Input } from './ui/input';

export function Navigation() {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Dashboard' },
    { path: '/scanner', label: 'Flow Scanner' },
    { path: '/alerts', label: 'Alerts' },
  ];
  
  return (
    <nav className="border-b border-white/10 bg-[#111827]">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo and Nav Items */}
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2">
              <Activity className="w-6 h-6 text-[#3B82F6]" />
              <span className="text-xl font-semibold text-[#E5E7EB]">FlowScope</span>
            </Link>
            
            <div className="flex items-center gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-4 py-2 rounded-md transition-colors ${
                    location.pathname === item.path
                      ? 'bg-[#3B82F6] text-white'
                      : 'text-[#9CA3AF] hover:text-[#E5E7EB] hover:bg-white/5'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          
          {/* Right side */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
              <Input
                type="text"
                placeholder="Search coin..."
                className="w-64 pl-10 bg-[#0B0F14] border-white/10 text-[#E5E7EB] placeholder:text-[#9CA3AF]"
              />
            </div>
            
            <button className="p-2 rounded-lg hover:bg-white/5 text-[#9CA3AF] hover:text-[#E5E7EB] transition-colors relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-[#EF4444] rounded-full"></span>
            </button>
            
            <button className="p-2 rounded-lg hover:bg-white/5 text-[#9CA3AF] hover:text-[#E5E7EB] transition-colors">
              <User className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
