import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, Download, FileSpreadsheet, FolderDown, ShieldAlert, Users } from "lucide-react";
import { getBatch, downloadOriginalFile } from "@/api/intake";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes, toPersianDigits } from "@/lib/utils";

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const batchId = Number(id);
  const { data: batch, isLoading, error } = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId),
    enabled: Number.isFinite(batchId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Spinner /> در حال بارگذاری…
      </div>
    );
  }
  if (error || !batch) {
    return (
      <div className="p-8 text-red-600">
        پرونده پیدا نشد یا به آن دسترسی ندارید.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl p-8">
      <Link to="/batches" className="text-sm text-slate-500 hover:text-slate-800">
        ← بازگشت به فهرست Batchها
      </Link>

      <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <FileSpreadsheet className="h-6 w-6 text-primary" />
            {batch.original_filename}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            شناسه #{toPersianDigits(batch.id)} • سال تحصیلی {batch.academic_year_label}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <a
              href="#"
              onClick={async (e) => {
                e.preventDefault();
                const resp = await downloadOriginalFile(batch.id);
                if (resp.ok) {
                  const blob = await resp.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = batch.original_filename;
                  a.click();
                  URL.revokeObjectURL(url);
                }
              }}
            >
              <Download className="h-4 w-4" /> دانلود فایل خام
            </a>
          </Button>
          {batch.processed_at && (
            <Button variant="outline" asChild>
              <Link to={`/batches/${batch.id}/exports`}>
                <FolderDown className="h-4 w-4" /> گزارش‌ها و خروجی
              </Link>
            </Button>
          )}
          {batch.processed_at && (
            <Button variant="outline" asChild>
              <Link to={`/batches/${batch.id}/review`}>
                <ShieldAlert className="h-4 w-4" />
                موارد نیازمند بررسی
              </Link>
            </Button>
          )}
          {batch.mapping_snapshot && (
            <Button asChild>
              <Link to={`/batches/${batch.id}/students`}>
                <Users className="h-4 w-4" />
                دانش‌آموزان و پردازش
              </Link>
            </Button>
          )}
          {batch.detected_columns.length > 0 ? (
            <Button variant="outline" asChild>
              <Link to={`/batches/${batch.id}/mapping`}>
                {batch.mapping_snapshot ? "ویرایش نگاشت" : "نگاشت ستون‌ها"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          ) : (
            <Button asChild>
              <Link to={`/batches/new?resume=${batch.id}`}>
                تکمیل انتخاب برگه و هدر <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="وضعیت" value={<Badge>{batch.status_display}</Badge>} />
        <Stat label="حجم فایل" value={formatBytes(batch.file_size)} />
        <Stat
          label="برگه"
          value={batch.selected_sheet || "—"}
        />
        <Stat
          label="تعداد ستون‌های شناسایی‌شده"
          value={toPersianDigits(batch.detected_columns.length)}
        />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">اطلاعات فایل</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-2">
            <dt className="text-slate-500">تاریخ آپلود</dt>
            <dd className="tnum">
              {new Date(batch.uploaded_at).toLocaleString("fa-IR")}
            </dd>
            <dt className="text-slate-500">سال تحصیلی</dt>
            <dd>{batch.academic_year_label}</dd>
            <dt className="text-slate-500">ردیف هدر</dt>
            <dd className="tnum">
              {batch.header_row_number ? toPersianDigits(batch.header_row_number) : "—"}
            </dd>
            <dt className="text-slate-500">تعداد برگه‌ها</dt>
            <dd className="tnum">{toPersianDigits(batch.workbook_sheets.length)}</dd>
          </dl>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">ستون‌های شناسایی‌شده</CardTitle>
        </CardHeader>
        <CardContent>
          {batch.detected_columns.length === 0 ? (
            <p className="text-sm text-slate-500">
              هنوز برگه و ردیف هدر انتخاب نشده است.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {batch.detected_columns.map((c) => (
                <span
                  key={c.index}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs"
                >
                  <span className="font-mono text-slate-400">{c.letter}</span>
                  <span>{c.label}</span>
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-slate-500">{label}</p>
        <p className="mt-1 text-lg font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}
