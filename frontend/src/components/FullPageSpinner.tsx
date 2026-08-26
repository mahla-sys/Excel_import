export default function FullPageSpinner() {
  return (
    <div className="flex h-full min-h-screen items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3 text-slate-500">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
        <span className="text-sm">در حال بارگذاری…</span>
      </div>
    </div>
  );
}
