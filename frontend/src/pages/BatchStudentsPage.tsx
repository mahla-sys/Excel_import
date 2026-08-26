import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import { PlayCircle, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { DataTable } from "@/components/ui/data-table";
import { StudentEditDialog } from "@/components/StudentEditDialog";
import {
  getBatch,
  listStagedStudents,
  processBatch,
  type StagedStudent,
} from "@/api/intake";
import { cn, maskNationalId, toPersianDigits } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  needs_review: "نیازمند بررسی",
  incomplete: "ناقص",
  validated: "معتبر",
  pending_placement: "در انتظار کلاس‌بندی",
  ready_for_future_integration: "آماده انتقال",
  archived: "بایگانی",
};

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "success" | "warning" | "destructive"
> = {
  validated: "success",
  pending_placement: "secondary",
  incomplete: "destructive",
  needs_review: "warning",
  draft: "secondary",
  ready_for_future_integration: "success",
  archived: "secondary",
};

export default function BatchStudentsPage() {
  const { id } = useParams<{ id: string }>();
  const batchId = Number(id);
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [editingStudent, setEditingStudent] = useState<number | null>(null);

  const batchQuery = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId),
  });

  const studentsQuery = useQuery({
    queryKey: ["batch-students", batchId, statusFilter],
    queryFn: () => listStagedStudents(batchId, statusFilter || undefined),
    enabled: Boolean(batchQuery.data?.mapping_snapshot),
  });

  const processMutation = useMutation({
    mutationFn: () => processBatch(batchId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batch", batchId] });
      qc.invalidateQueries({ queryKey: ["batch-students", batchId] });
    },
  });

  const columns: ColumnDef<StagedStudent>[] = [
    {
      accessorKey: "full_name",
      header: "نام و نام خانوادگی",
      cell: ({ row }) => (
        <span className="font-medium text-slate-800">{row.original.full_name}</span>
      ),
    },
    {
      accessorKey: "national_id",
      header: "کد ملی",
      cell: ({ row }) => {
        const nid = row.original.national_id;
        const valid = row.original.national_id_valid;
        return (
          <span className="tnum font-mono text-sm" dir="ltr">
            {nid ? maskNationalId(nid) : "—"}
            {nid && valid === false && (
              <Badge variant="destructive" className="mr-2">نامعتبر</Badge>
            )}
          </span>
        );
      },
    },
    {
      accessorKey: "grade",
      header: "پایه",
      cell: ({ row }) => row.original.grade || "—",
    },
    {
      id: "guardians",
      header: "ولی/والدین",
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {row.original.guardians.map((g) => (
            <span
              key={g.id}
              className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
            >
              {g.relation_display}: {g.full_name || g.first_name}
            </span>
          ))}
          {row.original.guardians.length === 0 && <span className="text-slate-400">—</span>}
        </div>
      ),
    },
    {
      accessorKey: "status",
      header: "وضعیت",
      cell: ({ row }) => (
        <Badge variant={STATUS_VARIANT[row.original.status] ?? "secondary"}>
          {STATUS_LABELS[row.original.status] ?? row.original.status}
        </Badge>
      ),
    },
  ];

  if (batchQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Spinner /> در حال بارگذاری…
      </div>
    );
  }
  const batch = batchQuery.data;
  if (!batch) return <div className="p-8">پرونده پیدا نشد.</div>;

  const hasMapping = Boolean(batch.mapping_snapshot);
  const stats = batch.stats || {};
  const hasBeenProcessed = Boolean(batch.processed_at);

  return (
    <div className="mx-auto max-w-6xl p-8">
      <Link to={`/batches/${batchId}`} className="text-sm text-slate-500 hover:text-slate-800">
        ← بازگشت به جزئیات Batch
      </Link>

      <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">دانش‌آموزان استخراج‌شده</h1>
          <p className="mt-1 text-sm text-slate-500">{batch.original_filename}</p>
        </div>
        {hasMapping && (
          <Button onClick={() => processMutation.mutate()} disabled={processMutation.isPending}>
            {processMutation.isPending ? <Spinner /> : <PlayCircle className="h-4 w-4" />}
            {hasBeenProcessed ? "پردازش مجدد" : "اجرای پردازش"}
          </Button>
        )}
      </header>

      {processMutation.error && (
        <Alert variant="destructive" className="mt-4">
          <TriangleAlert className="h-4 w-4" />
          <AlertTitle>پردازش ناموفق بود</AlertTitle>
          <AlertDescription>{(processMutation.error as Error).message}</AlertDescription>
        </Alert>
      )}

      {!hasMapping && (
        <Alert variant="warning" className="mt-4">
          <AlertTitle>ابتدا نگاشت ستون‌ها را انجام دهید</AlertTitle>
          <AlertDescription>
            برای استخراج دانش‌آموزان باید اول ستون‌های فایل را به فیلدهای استاندارد نگاشت کنید.
            <div className="mt-2">
              <Button asChild size="sm">
                <Link to={`/batches/${batchId}/mapping`}>رفتن به صفحه‌ی نگاشت</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {hasMapping && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            <StatTile label="کل سطرها" value={stats.total_rows} />
            <StatTile label="دانش‌آموزان" value={stats.created_students} tone="emerald" />
            <StatTile label="معتبر" value={stats.validated} tone="emerald" />
            <StatTile label="در انتظار کلاس" value={stats.pending_placement} tone="sky" />
            <StatTile label="ناقص/خطادار" value={stats.incomplete} tone="amber" />
            <StatTile label="هشدارها" value={stats.warnings} tone="amber" />
          </div>

          <div className="mt-6 flex items-center gap-2 text-sm">
            {[
              ["", "همه"],
              ["incomplete", "ناقص"],
              ["needs_review", "نیازمند بررسی"],
              ["pending_placement", "در انتظار کلاس‌بندی"],
              ["validated", "معتبر"],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setStatusFilter(value)}
                className={cn(
                  "rounded-md px-3 py-1 transition",
                  statusFilter === value
                    ? "bg-primary text-primary-foreground"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="mt-4">
            {studentsQuery.isLoading ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Spinner /> در حال بارگذاری…
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={studentsQuery.data ?? []}
                onRowClick={(s) => setEditingStudent(s.id)}
                emptyMessage={
                  hasBeenProcessed
                    ? "دانش‌آموزی با این وضعیت یافت نشد."
                    : "روی «اجرای پردازش» بزنید تا سطرهای فایل استخراج و نرمال‌سازی شوند."
                }
              />
            )}
          </div>
        </>
      )}

      <StudentEditDialog
        studentId={editingStudent}
        open={editingStudent !== null}
        onOpenChange={(o) => !o && setEditingStudent(null)}
      />
    </div>
  );
}

function StatTile({
  label, value, tone = "slate",
}: { label: string; value: number | undefined; tone?: "slate" | "emerald" | "sky" | "amber" }) {
  const tones: Record<string, string> = {
    slate: "text-slate-900",
    emerald: "text-emerald-600",
    sky: "text-sky-600",
    amber: "text-amber-600",
  };
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold tnum", tones[tone])}>
        {toPersianDigits(value ?? 0)}
      </p>
    </div>
  );
}
