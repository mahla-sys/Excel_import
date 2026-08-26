import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="text-6xl font-bold text-slate-300">404</p>
      <h1 className="mt-4 text-xl font-semibold text-slate-800">صفحه پیدا نشد</h1>
      <Link to="/" className="btn-primary mt-6">
        بازگشت به داشبورد
      </Link>
    </div>
  );
}
