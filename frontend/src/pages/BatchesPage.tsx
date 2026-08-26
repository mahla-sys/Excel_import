import { useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { Upload, FileSpreadsheet, Download } from "lucide-react";
import { DataTable } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import {
  downloadOriginalFile,
  listBatches,
  type ImportBatch,
} from "@/api/intake";
import { formatBytes, toPersianDigits } from "@/lib/utils";

function StatusBadge({ status }: { status: ImportBatch["status"] }) {
  const variant: Record<ImportBatch["status"], "default" | "secondary" | "warning" | "destructive" | "success"> = {
    uploaded: "secondary",
    mapping_required: "warning",
    processing: "default",
    review_required: "warning",
    validated: "success",
    approved_by_school: "success",
    ready_for_future_integration: "success",
    failed: "destructive",
    archived: "secondary",
  };
  const labels: Record<ImportBatch["status"], string> = {
    uploaded: "آپلود شد",
    mapping_required: "نیازمند نگاشت",
    processing: "در حال پردازش",
    review_required: "نیازمند بررسی",
    validated: "معتبر",
    approved_by_school: "تأیید مدرسه",
    ready_for_future_integration: "آماده‌ی انتقال آینده",
    failed: "ناموفق",
    archived: "بایگانی شد",
  };
  return <Badge variant={variant[status]}>{labels[status]}</Badge>;
}

export default function BatchesPage() {
  const { data: batches, isLoading, error } = useQuery({
    queryKey: ["batches"],
    queryFn: listBatches,
  });

  const downloadMutation = useMutation({
    mutationFn: async (id: number) => {
      const resp = await downloadOriginalFile(id);
      if (!resp.ok) throw new Error("دانلود ناموفق بود.");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `batch-${id}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const columns = useMemo<ColumnDef<ImportBatch>[]>(
    () => [
      {
        accessorKey: "id",
        header: "شناسه",
        cell: ({ row }) => (
          <Link to={`/batches/${row.original.id}`} className="font-medium text-primary hover:underline">
            #{toPersianDigits(row.original.id)}
          </Link>
        ),
      },
      { accessorKey: "original_filename", header: "نام فایل" },
      { accessorKey: "academic_year_label", header: "سال تحصیلی" },
      {
        accessorKey: "file_size",
        header: "حجم",
        cell: ({ row }) => (
          <span className="tnum text-slate-500">{formatBytes(row.original.file_size)}</span>
        ),
      },
      {
        accessorKey: "status",
        header: "وضعیت",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        accessorKey: "uploaded_at",
        header: "تاریخ آپلود",
        cell: ({ row }) => (
          <span className="tnum text-slate-500">
            {new Date(row.original.uploaded_at).toLocaleDateString("fa-IR")}
          </span>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                downloadMutation.mutate(row.original.id);
              }}
              title="دانلود فایل خام"
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        ),
      },
    ],
    [downloadMutation],
  );

  return (
    <div className="p-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <FileSpreadsheet className="h-6 w-6 text-primary" />
            فایل‌ها و Batchها
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            فایل‌های Excel ثبت‌نام مدرسه‌ی شما در این فهرست نگه‌داری می‌شوند.
          </p>
        </div>
        <Button asChild>
          <Link to="/batches/new">
            <Upload className="h-4 w-4" />
            آپلود فایل جدید
          </Link>
        </Button>
      </header>

      {isLoading ? (
        <div className="flex items-center gap-2 text-slate-500">
          <Spinner /> در حال بارگذاری…
        </div>
      ) : error ? (
        <p className="text-red-600">دریافت فهرست Batchها ناموفق بود.</p>
      ) : (
        <DataTable columns={columns} data={batches ?? []} onRowClick={(b) => (window.location.href = `/batches/${b.id}`)} />
      )}
    </div>
  );
}
