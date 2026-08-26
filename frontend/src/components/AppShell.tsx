import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { KeyRound, LogOut } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { ChangePasswordDialog } from "./ChangePasswordDialog";

type NavItem = {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
  soon?: boolean;
};

const baseNav: NavItem[] = [
  { to: "/", label: "داشبورد", icon: "🏠", end: true },
  { to: "/batches", label: "فایل‌ها و Batchها", icon: "📥" },
];

const adminNav: NavItem[] = [
  { to: "/admin/operators", label: "مدرسه‌ها و اپراتورها", icon: "🛡" },
  { to: "/admin/audit", label: "لاگ امنیتی", icon: "📜" },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "system_admin";
  const navItems = isAdmin ? [...baseNav, ...adminNav] : baseNav;
  const [pwdOpen, setPwdOpen] = useState(false);
  const forcedPwd = Boolean(user?.must_change_password);

  return (
    <div className="flex min-h-screen bg-slate-50" dir="rtl">
      <aside className="flex w-64 flex-col border-l border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-5">
          <h1 className="text-lg font-bold text-slate-900">پرتال ورود داده</h1>
          <p className="mt-1 text-xs text-slate-500">
            {isAdmin ? "پنل مدیر فنی" : "پنل مسئول مدرسه"}
          </p>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={(e) => {
                if (item.soon) e.preventDefault();
              }}
              className={({ isActive }) =>
                [
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                  item.soon
                    ? "cursor-not-allowed text-slate-400"
                    : isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-700 hover:bg-slate-100",
                ].join(" ")
              }
            >
              <span aria-hidden>{item.icon}</span>
              <span>{item.label}</span>
              {item.soon && (
                <span className="mr-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                  به‌زودی
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <div className="mb-3">
            <p className="text-sm font-semibold text-slate-800">
              {user?.full_name || user?.username}
            </p>
            <p className="text-xs text-slate-500">
              {user?.school ? user.school.name : user?.role_display}
            </p>
          </div>
          <div className="space-y-2">
            <button
              onClick={() => setPwdOpen(true)}
              className="flex w-full items-center justify-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              <KeyRound className="h-4 w-4" />
              تغییر رمز
            </button>
            <button onClick={logout} className="btn-secondary flex w-full items-center justify-center gap-2">
              <LogOut className="h-4 w-4" />
              خروج از حساب
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <Outlet />
      </main>

      <ChangePasswordDialog
        forced={forcedPwd}
        open={forcedPwd || pwdOpen}
        onOpenChange={(o) => {
          // Forced dialog cannot be dismissed until the password changes.
          if (!forcedPwd) setPwdOpen(o);
        }}
      />
    </div>
  );
}
