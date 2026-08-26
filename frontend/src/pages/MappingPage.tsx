import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  CheckCircle2,
  Filter,
  Save,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import {
  fetchCanonicalFields,
  fetchSuggestions,
  getBatch,
  saveBatchMapping,
  type CanonicalField,
  type ColumnInfo,
  type ImportBatch,
  type Suggestion,
  type UnknownColumn,
} from "@/api/intake";
import { cn, toPersianDigits } from "@/lib/utils";

type FilterMode = "all" | "unmapped" | "duplicate";

interface LocalAssignment {
  target: string; // canonical field path, or "" for unmapped
  action: "map" | "extra" | "ignore"; // for unmapped columns
  ignoreReason?: string;
}

export default function MappingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const batchId = Number(id);

  const batchQuery = useQuery<ImportBatch>({
    queryKey: ["batch", batchId],
    queryFn: () => getBatch(batchId),
  });
  const fieldsQuery = useQuery({
    queryKey: ["canonical-fields"],
    queryFn: fetchCanonicalFields,
    staleTime: 5 * 60 * 1000,
  });
  const suggestionsQuery = useQuery({
    queryKey: ["suggestions", batchId],
    queryFn: () => fetchSuggestions(batchId),
    enabled: Boolean(batchQuery.data?.detected_columns.length),
  });

  const columns = batchQuery.data?.detected_columns ?? [];

  // Pre-seed assignments from snapshot (if mapping already saved) or suggestions.
  const [assignments, setAssignments] = useState<Record<number, LocalAssignment>>({});
  const [profileName, setProfileName] = useState("");
  const [saveMessage, setSaveMessage] = useState<{ kind: "ok" | "warn"; text: string } | null>(null);

  useEffect(() => {
    if (!columns.length) return;
    const snapshot = batchQuery.data?.mapping_snapshot?.mappings ?? {};
    // Invert snapshot: source_index -> canonical path
    const byIndex: Record<number, string> = {};
    for (const [canonical, tgt] of Object.entries(snapshot)) {
      byIndex[tgt.source_column_index] = canonical;
    }

    const next: Record<number, LocalAssignment> = {};
    const suggestions = suggestionsQuery.data?.suggestions ?? [];
    for (const col of columns) {
      if (byIndex[col.index] !== undefined) {
        next[col.index] = { target: byIndex[col.index], action: "map" };
        continue;
      }
      const s = suggestions.find((x) => x.column_index === col.index);
      if (s?.target && (s.confidence === "high" || s.confidence === "medium")) {
        next[col.index] = { target: s.target, action: "map" };
      } else {
        next[col.index] = { target: "", action: "extra" };
      }
    }
    setAssignments(next);
  }, [columns, suggestionsQuery.data, batchQuery.data?.mapping_snapshot]);

  const duplicateLabelSet = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of columns) counts[c.label] = (counts[c.label] ?? 0) + 1;
    return new Set(Object.keys(counts).filter((k) => counts[k] > 1));
  }, [columns]);

  const canonicalPathOptions = useMemo(() => {
    const fields: CanonicalField[] = fieldsQuery.data?.fields ?? [];
    return fields;
  }, [fieldsQuery.data]);

  const fieldsByPath = useMemo(() => {
    const m = new Map<string, CanonicalField>();
    for (const f of canonicalPathOptions) m.set(f.path, f);
    return m;
  }, [canonicalPathOptions]);

  const [filter, setFilter] = useState<FilterMode>("all");

  const visibleColumns = useMemo(() => {
    return columns.filter((c) => {
      if (filter === "unmapped") return !assignments[c.index]?.target;
      if (filter === "duplicate") return duplicateLabelSet.has(c.label);
      return true;
    });
  }, [columns, filter, assignments, duplicateLabelSet]);

  const usedTargets = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of Object.values(assignments)) {
      if (a.target) m.set(a.target, (m.get(a.target) ?? 0) + 1);
    }
    return m;
  }, [assignments]);

  const stats = useMemo(() => {
    const mapped = columns.filter((c) => assignments[c.index]?.target).length;
    const ignored = columns.filter((c) => assignments[c.index]?.action === "ignore").length;
    const extra = columns.filter((c) => !assignments[c.index]?.target && assignments[c.index]?.action === "extra").length;
    return {
      total: columns.length,
      mapped,
      ignored,
      extra,
      unmapped: columns.length - mapped - ignored,
    };
  }, [columns, assignments]);

  const saveMutation = useMutation({
    mutationFn: (acceptSuggestions: boolean) => {
      const mappings: Record<string, { source_column_index: number; source_column_label: string }> = {};
      const unknown: UnknownColumn[] = [];
      for (const col of columns) {
        const a = assignments[col.index];
        if (!a) continue;
        if (a.target) {
          mappings[a.target] = {
            source_column_index: col.index,
            source_column_label: col.label,
          };
        } else if (a.action === "ignore") {
          unknown.push({ index: col.index, label: col.label, action: "ignored" });
        } else {
          unknown.push({ index: col.index, label: col.label, action: "extra_attribute" });
        }
      }
      return saveBatchMapping(batchId, {
        mappings: acceptSuggestions ? undefined : mappings,
        unknown_columns: unknown,
        save_as_profile: profileName || undefined,
        accept_suggestions: acceptSuggestions,
      });
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["batch", batchId] });
      qc.invalidateQueries({ queryKey: ["batches"] });
      if (data.consistency_warnings?.length) {
        setSaveMessage({
          kind: "warn",
          text: "نگاشت ذخیره شد، اما چند هشدار وجود دارد: " + data.consistency_warnings.join(" — "),
        });
      } else {
        setSaveMessage({ kind: "ok", text: "نگاشت با موفقیت ذخیره شد." });
        setTimeout(() => navigate(`/batches/${batchId}`), 1000);
      }
    },
    onError: (err: Error) => {
      setSaveMessage({ kind: "warn", text: err.message });
    },
  });

  if (batchQuery.isLoading || fieldsQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 p-8 text-slate-500">
        <Spinner /> در حال بارگذاری…
      </div>
    );
  }
  if (!batchQuery.data) {
    return <div className="p-8 text-red-600">پرونده پیدا نشد.</div>;
  }

  const batch = batchQuery.data;
  if (!batch.detected_columns.length) {
    return (
      <div className="p-8">
        <Alert variant="warning">
          <AlertTitle>ابتدا ردیف هدر را انتخاب کنید</AlertTitle>
          <AlertDescription>
            برای نگاشت ستون‌ها باید اول در ویزارد آپلود برگه و ردیف عنوان ستون‌ها را مشخص کنید.
          </AlertDescription>
        </Alert>
        <div className="mt-4">
          <Button asChild>
            <Link to={`/batches/new?resume=${batchId}`}>رفتن به ویزارد آپلود</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-8">
      <Link to={`/batches/${batchId}`} className="text-sm text-slate-500 hover:text-slate-800">
        ← بازگشت به جزئیات Batch
      </Link>

      <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">نگاشت ستون‌ها به فیلدهای استاندارد</h1>
          <p className="mt-1 text-sm text-slate-500">
            فایل «{batch.original_filename}» — {toPersianDigits(columns.length)} ستون
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => saveMutation.mutate(true)}
            disabled={saveMutation.isPending}
          >
            <Sparkles className="h-4 w-4" />
            پذیرش پیشنهادهای سامانه
          </Button>
          <Button onClick={() => saveMutation.mutate(false)} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? <Spinner /> : <Save className="h-4 w-4" />}
            ذخیره نگاشت
          </Button>
        </div>
      </header>

      {saveMessage && (
        <Alert
          className="mt-4"
          variant={saveMessage.kind === "ok" ? "default" : "warning"}
        >
          {saveMessage.kind === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <TriangleAlert className="h-4 w-4" />}
          <AlertTitle>{saveMessage.kind === "ok" ? "ذخیره شد" : "توجه"}</AlertTitle>
          <AlertDescription>{saveMessage.text}</AlertDescription>
        </Alert>
      )}

      {/* Stats */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="کل ستون‌ها" value={toPersianDigits(stats.total)} />
        <StatCard label="نگاشت‌شده" value={toPersianDigits(stats.mapped)} tone="emerald" />
        <StatCard label="ذخیره به‌عنوان اطلاعات تکمیلی" value={toPersianDigits(stats.extra)} tone="sky" />
        <StatCard label="بدون اقدام" value={toPersianDigits(stats.unmapped)} tone="amber" />
      </div>

      <Card className="mt-6">
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">ستون‌های فایل</CardTitle>
          <div className="flex items-center gap-2 text-sm">
            <Filter className="h-4 w-4 text-slate-400" />
            {([
              ["all", "همه"],
              ["unmapped", "نگاشت‌نشده"],
              ["duplicate", "ستون‌های تکراری"],
            ] as [FilterMode, string][]).map(([mode, label]) => (
              <button
                key={mode}
                onClick={() => setFilter(mode)}
                className={cn(
                  "rounded-md px-3 py-1",
                  filter === mode ? "bg-primary text-primary-foreground" : "bg-slate-100 text-slate-600",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="w-12 px-3 py-2 text-right">ستون</th>
                  <th className="px-3 py-2 text-right">عنوان فایل</th>
                  <th className="px-3 py-2 text-right">نمونه مقادیر</th>
                  <th className="px-3 py-2 text-right">پیشنهاد سامانه</th>
                  <th className="px-3 py-2 text-right">نگاشت به</th>
                  <th className="px-3 py-2 text-right">رفتار</th>
                </tr>
              </thead>
              <tbody>
                {visibleColumns.map((col) => (
                  <ColumnRow
                    key={col.index}
                    col={col}
                    assignment={assignments[col.index] ?? { target: "", action: "extra" }}
                    suggestion={suggestionsQuery.data?.suggestions.find(
                      (s) => s.column_index === col.index,
                    )}
                    isDuplicate={duplicateLabelSet.has(col.label)}
                    canonicalOptions={canonicalPathOptions}
                    fieldsByPath={fieldsByPath}
                    usedCount={assignments[col.index]?.target ? usedTargets.get(assignments[col.index].target!) ?? 0 : 0}
                    onChange={(next) =>
                      setAssignments((prev) => ({ ...prev, [col.index]: next }))
                    }
                  />
                ))}
                {visibleColumns.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      ستونی برای نمایش در این فیلتر وجود ندارد.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">ذخیره به‌عنوان الگوی نگاشت</CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="profile-name">
            نام الگو (اختیاری — برای استفاده‌ی مجدد در آپلودهای بعدی همین مدرسه)
          </Label>
          <Input
            id="profile-name"
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            placeholder="مثلاً: قالب ثبت‌نام ۱۴۰۵"
            className="mt-2 max-w-md"
          />
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------

interface ColumnRowProps {
  col: ColumnInfo;
  assignment: LocalAssignment;
  suggestion?: Suggestion;
  isDuplicate: boolean;
  canonicalOptions: CanonicalField[];
  fieldsByPath: Map<string, CanonicalField>;
  usedCount: number;
  onChange: (a: LocalAssignment) => void;
}

function ColumnRow({
  col, assignment, suggestion, isDuplicate, canonicalOptions, fieldsByPath, usedCount, onChange,
}: ColumnRowProps) {
  const targetLabel = assignment.target
    ? fieldsByPath.get(assignment.target)?.label ?? assignment.target
    : "";
  const duplicateTarget = assignment.target && usedCount > 1;

  return (
    <tr className="border-t align-top">
      <td className="px-3 py-3">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 font-mono text-xs text-slate-600">
          {col.letter}
        </span>
      </td>
      <td className="px-3 py-3">
        <div className="font-medium text-slate-800">{col.label}</div>
        {isDuplicate && (
          <Badge variant="warning" className="mt-1">
            عنوان تکراری — موقعیت {col.letter}
          </Badge>
        )}
      </td>
      <td className="px-3 py-3">
        <div className="flex flex-wrap gap-1">
          {col.samples.slice(0, 3).map((s) => (
            <span key={s} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {s || "—"}
            </span>
          ))}
        </div>
      </td>
      <td className="px-3 py-3">
        {suggestion && suggestion.target ? (
          <div className="space-y-1">
            <Badge
              variant={
                suggestion.confidence === "high"
                  ? "success"
                  : suggestion.confidence === "medium"
                    ? "warning"
                    : "secondary"
              }
            >
              {suggestion.target_label}
            </Badge>
            {suggestion.reason && (
              <p className="text-xs text-slate-500">{suggestion.reason}</p>
            )}
          </div>
        ) : (
          <span className="text-xs text-slate-400">پیشنهادی موجود نیست</span>
        )}
      </td>
      <td className="px-3 py-3">
        <select
          value={assignment.target}
          onChange={(e) => onChange({ ...assignment, target: e.target.value, action: e.target.value ? "map" : assignment.action })}
          className={cn(
            "w-64 rounded-md border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring",
            duplicateTarget && "border-amber-400 ring-1 ring-amber-300",
          )}
        >
          <option value="">— نگاشت نشده —</option>
          {canonicalOptions.map((opt) => (
            <option key={opt.path} value={opt.path}>
              {opt.label} ({opt.path})
            </option>
          ))}
        </select>
        {duplicateTarget && (
          <p className="mt-1 text-xs text-amber-700">
            این فیلد استاندارد به یک ستون دیگر هم نگاشت شده است.
          </p>
        )}
        {targetLabel && <p className="mt-1 text-xs text-slate-400">{targetLabel}</p>}
      </td>
      <td className="px-3 py-3">
        {!assignment.target && (
          <select
            value={assignment.action}
            onChange={(e) =>
              onChange({
                ...assignment,
                action: e.target.value as LocalAssignment["action"],
              })
            }
            className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          >
            <option value="extra">ذخیره در اطلاعات تکمیلی</option>
            <option value="ignore">نادیده گرفتن</option>
          </select>
        )}
      </td>
    </tr>
  );
}

function StatCard({
  label, value, tone = "slate",
}: { label: string; value: string; tone?: "slate" | "emerald" | "sky" | "amber" }) {
  const tones: Record<string, string> = {
    slate: "text-slate-900",
    emerald: "text-emerald-600",
    sky: "text-sky-600",
    amber: "text-amber-600",
  };
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-slate-500">{label}</p>
        <p className={cn("mt-1 text-xl font-bold", tones[tone])}>{value}</p>
      </CardContent>
    </Card>
  );
}
