import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { listAuditLog, type AuditEntry } from "@/api/intake";
import { toPersianDigits } from "@/lib/utils";

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "ورود",
  "batch.upload": "آپلود",
  "batch.process": "پردازش",
  "batch.approve": "تأیید",
  "batch.archive": "بایگانی",
  "batch.download_raw": "دانلود فایل خام",
  "student.update": "ویرایش دانش‌آموز",
  "student.status_change": "رفع ابهام",
  "mapping_profile.create": "ساخت پروفایل نگاشت",
  "export.errors": "دانلود گزارش خطاها",
  "export.canonical": "دانلود خروجی استاندارد",
};

export default function AuditLogPage() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["audit-log", action, entity],
    queryFn: () => listAuditLog({ action, entity_type: entity }),
  });

  return (
    <div className="mx-auto max-w-6xl p-8">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <ShieldAlert className="h-6 w-6 text-primary" />
        لاگ امنیتی
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        همه‌ی عملیات حساس (ورود، آپلود، دانلود، ویرایش، تأیید) با کاربر، زمان و مدرسه ثبت می‌شوند.
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <Input
          placeholder="فیلتر بر اساس نوع عملیات (مثلاً batch.upload)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          dir="ltr"
        />
        <Input
          placeholder="فیلتر بر اساس نوع موجودیت (مثلاً StagedStudent)"
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          dir="ltr"
        />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-base">
            آخرین رویدادها ({toPersianDigits((data ?? []).length)})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 text-slate-500"><Spinner /> در حال بارگذاری…</div>
          ) : (
            <ul className="divide-y text-sm">
              {(data ?? []).map((e: AuditEntry) => (
                <li key={e.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <Badge variant="secondary" className="font-mono text-[11px]" dir="ltr">
                    {ACTION_LABELS[e.action] ?? e.action}
                  </Badge>
                  <span className="text-slate-600">
                    <strong>{e.actor_username}</strong> روی{" "}
                    <span className="font-mono text-xs">
                      {e.entity_type}#{e.entity_id}
                    </span>
                    {e.school_name ? ` در ${e.school_name}` : ""}
                  </span>
                  <span className="mr-auto text-xs text-slate-400 tnum">
                    {new Date(e.created_at).toLocaleString("fa-IR")}
                  </span>
                </li>
              ))}
              {data && data.length === 0 && (
                <li className="p-6 text-center text-slate-500">رویدادی یافت نشد.</li>
              )}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
