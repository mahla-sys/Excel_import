import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { type ColumnDef } from "@tanstack/react-table";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  RefreshCw,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { DataTable } from "@/components/ui/data-table";
import { StudentEditDialog } from "@/components/StudentEditDialog";
import { DuplicateResolveDialog } from "@/components/DuplicateResolveDialog";
import {
  approveBatch,
  getBatch,
  listStagedStudents,
  revalidateBatch,
  type StagedStudent,
} from "@/api/intake";
import { cn, maskNationalId, toPersianDigits } from "@/lib/utils";

type ReviewIssue = {
  code?: string;
  severity?: string;
  field?: string;
  message?: string;
  other_student_ids?: number[];
  previous_batch_id?: number;
};

const STATUS_LABELS: Record<string, string> = {
  incomplete: "ناقص",
  needs_review: "نیازمند بررسی",
  pending_placement: "در انتظار کلاس‌بندی",
  validated: "معتبر",
};

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "success" | "warning" | "destructive"
> = {
  incomplete: "destructive",
  needs_review: "warning",
  pending_placement: "secondary",
  validated: "success",
};

const REVIEW_TABS = [
  { key: "incomplete", label: "ناقص", icon: AlertTriangle },
  { key: "needs_review", label: "نیازمند بررسی", icon: ShieldAlert },
  { key: "duplicates", label: "مشکوک به تکرار", icon: ClipboardCheck },
  { key: "pending_placement", label: "در انتظار کلاس‌بندی", icon: CheckCircle2 },
  { key: "validated", label: "معتبر", icon: CheckCircle2 },
] as const;

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const batchId = Number(id);
  const qc = useQueryClient();
  const [tab, setTab] = useState<(typeof REVIEW_TABS)[number]["key"]>("incomplete");

  const batchQuery = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId),
  });

  const [editingStudent, setEditingStudent] = useState<number | null>(null);
  const [resolveTarget, setResolveTarget] = useState<{ studentId: number; issueCode: string } | null>(null);

  const studentsQuery = useQuery({
    queryKey: ["batch-students", batchId],
    queryFn: () => listStagedStudents(batchId),
    enabled: Boolean(batchQuery.data?.processed_at),
  });

  const students = studentsQuery.data ?? [];

  const filtered = useMemo(() => {
    if (tab === "duplicates") {
      return students.filter((s) =>
        (s as StagedStudent & { validation_issues?: ReviewIssue[] }).validation_issues?.some(
          (i) => i.code === "W-DUPLICATE-EXACT" || i.code === "W-DUPLICATE-SUSPECTED",
        ),
      );
    }
    return students.filter((s) => s.status === tab);
  }, [students, tab]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {
      incomplete: 0, needs_review: 0, pending_placement: 0, validated: 0, duplicates: 0,
    };
    for (const s of students) {
      c[s.status] = (c[s.status] ?? 0) + 1;
      const issues = (s as StagedStudent & { validation_issues?: ReviewIssue[] }).validation_issues ?? [];
      if (issues.some((i) => i.code?.startsWith("W-DUPLICATE"))) c.duplicates += 1;
    }
    return c;
  }, [students]);

  const revalidateMut = useMutation({
    mutationFn: () => revalidateBatch(batchId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batch", batchId] });
      qc.invalidateQueries({ queryKey: ["batch-students", batchId] });
    },
  });
  const approveMut = useMutation({
    mutationFn: () => approveBatch(batchId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["batch", batchId] }),
  });

  const columns: ColumnDef<StagedStudent>[] = [
    {
      accessorKey: "full_name",
      header: "نام",
      cell: ({ row }) => (
        <div>
          <div className="font-medium text-slate-800">{row.original.full_name}</div>
          <div className="mt-1 flex flex-wrap gap-1 text-xs text-slate-500 tnum" dir="ltr">
            <span>{maskNationalId(row.original.national_id)}</span>
            {row.original.grade && <span>• پایه {row.original.grade}</span>}
          </div>
        </div>
      ),
    },
    {
      id: "issues",
      header: "مشکلات و هشدارها",
      cell: ({ row }) => {
        const s = row.original as StagedStudent & {
          validation_issues?: ReviewIssue[];
          duplicate_resolutions?: { issue_code: string }[];
        };
        const issues = s.validation_issues ?? [];
        if (!issues.length) return <span className="text-xs text-emerald-600">بدون مشکل</span>;
        const resolved = new Set((s.duplicate_resolutions ?? []).map((r) => r.issue_code));
        return (
          <ul className="max-w-md space-y-1">
            {issues.slice(0, 4).map((i, idx) => {
              const isIdentity = i.code?.startsWith("W-DUPLICATE") || i.code?.startsWith("E-NID");
              const isResolved = i.code && resolved.has(i.code);
              return (
                <li
                  key={idx}
                  className={cn(
                    "flex flex-wrap items-start gap-1 text-xs",
                    i.severity === "error" ? "text-red-700"
                      : i.severity === "warning" ? "text-amber-700"
                      : "text-slate-500",
                    isResolved && "text-emerald-700 line-through decoration-emerald-400/50",
                  )}
                >
                  {i.severity === "error" ? (
                    <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />
                  ) : (
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  )}
                  <span>{i.message || i.code}</span>
                  {i.other_student_ids && i.other_student_ids.length > 0 && (
                    <span className="text-slate-400">
                      (رکوردها: {i.other_student_ids.map(toPersianDigits).join("، ")})
                    </span>
                  )}
                  {isIdentity && !isResolved && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setResolveTarget({ studentId: row.original.id, issueCode: i.code! });
                      }}
                      className="mr-auto rounded bg-primary px-2 py-0.5 text-[11px] text-primary-foreground hover:bg-primary/90"
                    >
                      رفع ابهام
                    </button>
                  )}
                  {isResolved && (
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-800">
                      تصمیم ثبت شد
                    </span>
                  )}
                </li>
              );
            })}
            {issues.length > 4 && (
              <li className="text-xs text-slate-400">
                و {toPersianDigits(issues.length - 4)} مورد دیگر…
              </li>
            )}
          </ul>
        );
      },
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

  const batch = batchQuery.data;
  const canApprove = batch && (counts.incomplete ?? 0) === 0 && (counts.needs_review ?? 0) === 0;
  const blockingCount = (counts.incomplete ?? 0) + (counts.needs_review ?? 0);

  return (
    <div className="mx-auto max-w-6xl p-8">
      <Link to={`/batches/${batchId}`} className="text-sm text-slate-500 hover:text-slate-800">
        ← بازگشت به جزئیات Batch
      </Link>

      <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ShieldAlert className="h-6 w-6 text-amber-500" />
            موارد نیازمند بررسی
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {batch?.original_filename}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => revalidateMut.mutate()}
            disabled={revalidateMut.isPending}
          >
            <RefreshCw className={cn("h-4 w-4", revalidateMut.isPending && "animate-spin")} />
            بررسی مجدد
          </Button>
          <Button
            onClick={() => approveMut.mutate()}
            disabled={!canApprove || approveMut.isPending}
          >
            {approveMut.isPending ? <Spinner /> : <CheckCircle2 className="h-4 w-4" />}
            تأیید نهایی مدرسه
          </Button>
        </div>
      </header>

      {approveMut.error && (
        <Alert variant="destructive" className="mt-4">
          <AlertTitle>تأیید ناموفق</AlertTitle>
          <AlertDescription>{(approveMut.error as Error).message}</AlertDescription>
        </Alert>
      )}
      {approveMut.isSuccess && (
        <Alert className="mt-4">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <AlertTitle>تأیید شد</AlertTitle>
          <AlertDescription>
            این Batch به‌عنوان «تأییدشده توسط مدرسه» علامت خورد و برای انتقال
            آینده آماده است.
          </AlertDescription>
        </Alert>
      )}

      {blockingCount > 0 && (
        <Alert variant="warning" className="mt-4">
          <AlertTitle>
            {toPersianDigits(blockingCount)} پرونده هنوز قابل تأیید نیست
          </AlertTitle>
          <AlertDescription>
            تا رفع نقص پرونده‌های ناقص و موارد نیازمند بررسی، دکمه‌ی تأیید نهایی
            غیرفعال است.
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-6 flex flex-wrap gap-2">
        {REVIEW_TABS.map((t) => {
          const count = counts[t.key] ?? 0;
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "bg-white text-slate-600 hover:bg-slate-50",
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{t.label}</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs tnum",
                  active ? "bg-white/20" : "bg-slate-100 text-slate-600",
                )}
              >
                {toPersianDigits(count)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-4">
        {studentsQuery.isLoading ? (
          <div className="flex items-center gap-2 text-slate-500">
            <Spinner /> در حال بارگذاری…
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filtered}
            emptyMessage="در این دسته موردی یافت نشد."
            onRowClick={(s) => setEditingStudent(s.id)}
          />
        )}
      </div>

      <StudentEditDialog
        studentId={editingStudent}
        open={editingStudent !== null}
        onOpenChange={(o) => !o && setEditingStudent(null)}
      />
      <DuplicateResolveDialog
        studentId={resolveTarget?.studentId ?? null}
        issueCode={resolveTarget?.issueCode ?? null}
        open={resolveTarget !== null}
        onOpenChange={(o) => !o && setResolveTarget(null)}
      />
    </div>
  );
}
