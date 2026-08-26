import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  Download,
  FileJson,
  FileSpreadsheet,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import {
  downloadCanonicalJson,
  downloadCanonicalXlsx,
  downloadErrorReport,
} from "@/api/intake";

export default function ExportsPage() {
  const { id } = useParams<{ id: string }>();
  const batchId = Number(id);
  const [error, setError] = useState<string | null>(null);

  const errorsMut = useMutation({ mutationFn: () => downloadErrorReport(batchId), onError: (e: Error) => setError(e.message) });
  const xlsxMut = useMutation({ mutationFn: () => downloadCanonicalXlsx(batchId), onError: (e: Error) => setError(e.message) });
  const jsonMut = useMutation({ mutationFn: () => downloadCanonicalJson(batchId), onError: (e: Error) => setError(e.message) });

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link to={`/batches/${batchId}`} className="text-sm text-slate-500 hover:text-slate-800">
        ← بازگشت به جزئیات Batch
      </Link>

      <header className="mt-4">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Download className="h-6 w-6 text-primary" />
          گزارش‌ها و خروجی‌ها
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          خروجی‌ها فقط برای مدرسه‌ی شما در دسترس‌اند و هر دانلود در لاگ امنیتی ثبت می‌شود.
        </p>
      </header>

      {error && (
        <Alert variant="destructive" className="mt-4">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>خطا در دانلود</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              گزارش خطاها (Excel)
            </CardTitle>
            <CardDescription>
              فهرست پرونده‌های ناقص یا نیازمند بررسی به‌همراه پیام هر خطا/هشدار و پیشنهاد اقدام.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => errorsMut.mutate()} disabled={errorsMut.isPending}>
              {errorsMut.isPending ? <Spinner /> : <FileSpreadsheet className="h-4 w-4" />}
              دانلود XLSX
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileSpreadsheet className="h-5 w-5 text-emerald-500" />
              خروجی استاندارد (Excel)
            </CardTitle>
            <CardDescription>
              تمام دانش‌آموزان با فیلدهای استاندارد در یک شیت و والدین در شیت دوم.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => xlsxMut.mutate()} disabled={xlsxMut.isPending}>
              {xlsxMut.isPending ? <Spinner /> : <Download className="h-4 w-4" />}
              دانلود XLSX
            </Button>
          </CardContent>
        </Card>

        <Card className="sm:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileJson className="h-5 w-5 text-sky-500" />
              خروجی استاندارد نسخه‌بندی‌شده (JSON)
            </CardTitle>
            <CardDescription>
              قرارداد پایدار برای اتصال به سیستم اصلی در آینده. حاوی{" "}
              <code className="rounded bg-slate-100 px-1">schema_version</code>،
              شناسه‌ی پایدار مدرسه (<code>external_code</code>) و هش فایل.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <p className="flex items-center gap-1 text-xs text-slate-500">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              فرمول‌های مخرب در سلول‌ها خنثی می‌شوند.
            </p>
            <Button onClick={() => jsonMut.mutate()} disabled={jsonMut.isPending}>
              {jsonMut.isPending ? <Spinner /> : <Download className="h-4 w-4" />}
              دانلود JSON
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
