import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  Upload,
  Users,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { fetchDashboard } from "@/api/intake";
import { useAuth } from "@/auth/AuthContext";
import { cn, toPersianDigits } from "@/lib/utils";

const BATCH_STATUS_LABELS: Record<string, string> = {
  uploaded: "آپلود شد",
  mapping_required: "نیازمند نگاشت",
  processing: "در حال پردازش",
  review_required: "نیازمند بررسی",
  validated: "اعتبارسنجی شد",
  approved_by_school: "تأیید مدرسه",
  ready_for_future_integration: "آماده انتقال",
  failed: "ناموفق",
  archived: "بایگانی",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Spinner /> در حال بارگذاری…
      </div>
    );
  }
  if (error || !data) {
    return <div className="p-8 text-red-600">دریافت اطلاعات داشبورد ناموفق بود.</div>;
  }

  const s = data.student_status_counts;
  const b = data.batch_status_counts;
  const isAdmin = !user?.school;

  return (
    <div className="mx-auto max-w-6xl p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">
            {isAdmin
              ? "پنل مدیر سامانه"
              : `داشبورد ${data.school?.name ?? ""}`}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {isAdmin
              ? "مدیریت مدرسه‌ها، اپراتورها و مشاهده‌ی لاگ امنیتی."
              : "خلاصه‌ی وضعیت فایل‌های ثبت‌نام و دانش‌آموزان مدرسه‌ی شما."}
          </p>
        </div>
        {!isAdmin && (
          <Button asChild>
            <Link to="/batches/new">
              <Upload className="h-4 w-4" /> آپلود فایل جدید
            </Link>
          </Button>
        )}
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          icon={<FileSpreadsheet className="h-5 w-5 text-sky-600" />}
          label="کل Batchها"
          value={data.totals.batches}
        />
        <StatTile
          icon={<Users className="h-5 w-5 text-emerald-600" />}
          label="دانش‌آموزان استیج‌شده"
          value={data.totals.students}
        />
        <StatTile
          icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
          label="تأییدشده توسط مدرسه"
          value={b.approved_by_school ?? 0}
        />
        <StatTile
          icon={<Clock className="h-5 w-5 text-amber-600" />}
          label="نیازمند بررسی"
          value={b.review_required ?? 0}
          tone="amber"
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">آخرین فایل‌های آپلودشده</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {data.recent_batches.length === 0 ? (
              <p className="p-6 text-center text-sm text-slate-500">
                هنوز فایلی آپلود نشده است.
              </p>
            ) : (
              <ul className="divide-y">
                {data.recent_batches.map((b) => (
                  <li key={b.id}>
                    <Link
                      to={`/batches/${b.id}`}
                      className="flex items-center justify-between gap-3 px-6 py-3 hover:bg-slate-50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800">
                          {b.original_filename}
                        </p>
                        <p className="text-xs text-slate-500 tnum">
                          سال {b.academic_year_label} •{" "}
                          {new Date(b.uploaded_at).toLocaleDateString("fa-IR")}
                        </p>
                      </div>
                      <Badge
                        variant={
                          b.status === "approved_by_school"
                            ? "success"
                            : b.status === "failed"
                              ? "destructive"
                              : b.status === "review_required"
                                ? "warning"
                                : "secondary"
                        }
                      >
                        {BATCH_STATUS_LABELS[b.status] ?? b.status}
                      </Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">وضعیت دانش‌آموزان</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <StatusRow
              icon={<XCircle className="h-4 w-4 text-red-600" />}
              label="ناقص"
              value={s.incomplete ?? 0}
            />
            <StatusRow
              icon={<Clock className="h-4 w-4 text-amber-600" />}
              label="نیازمند بررسی"
              value={s.needs_review ?? 0}
            />
            <StatusRow
              icon={<Clock className="h-4 w-4 text-sky-600" />}
              label="در انتظار کلاس‌بندی"
              value={s.pending_placement ?? 0}
            />
            <StatusRow
              icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />}
              label="معتبر"
              value={s.validated ?? 0}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatTile({
  icon, label, value, tone = "slate",
}: { icon: React.ReactNode; label: string; value: number; tone?: "slate" | "amber" }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-full bg-slate-100 p-2">{icon}</div>
        <div>
          <p className="text-xs text-slate-500">{label}</p>
          <p
            className={cn(
              "mt-0.5 text-2xl font-bold tnum",
              tone === "amber" ? "text-amber-600" : "text-slate-900",
            )}
          >
            {toPersianDigits(value)}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusRow({
  icon, label, value,
}: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="flex items-center gap-2 text-slate-600">
        {icon}
        {label}
      </span>
      <span className="font-semibold tnum text-slate-900">{toPersianDigits(value)}</span>
    </div>
  );
}
