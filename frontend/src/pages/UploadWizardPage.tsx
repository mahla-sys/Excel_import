import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  Upload as UploadIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import {
  selectHeader,
  selectSheet,
  uploadBatch,
  type ColumnInfo,
  type ImportBatch,
  type SheetInfo,
} from "@/api/intake";
import { cn, formatBytes, toPersianDigits } from "@/lib/utils";

const MAX_FILE_MB = 10;
const STEPS = ["انتخاب فایل", "برگه و هدر", "بررسی ستون‌ها"];

/** Suggest the current Jalali academic year as 1404-1405 style, prefixed by today. */
function suggestAcademicYear(): string {
  const now = new Date();
  const gregYear = now.getFullYear();
  const month = now.getMonth() + 1;
  // Approximate Jalali year (sufficient for a default suggestion; the
  // operator confirms it before upload).
  const jy = gregYear - 621;
  // Academic year in Iran typically starts Mehr (month 9 in Gregorian).
  const startYear = month >= 9 ? jy : jy - 1;
  return `${startYear}-${startYear + 1}`;
}

export default function UploadWizardPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);

  // Step 0 form state
  const [file, setFile] = useState<File | null>(null);
  const [academicYear, setAcademicYear] = useState(suggestAcademicYear());
  const [notes, setNotes] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);

  // Created batch after upload succeeds
  const [batch, setBatch] = useState<ImportBatch | null>(null);

  // Step 1 selections
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [headerRow, setHeaderRow] = useState<number>(1);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("فایل انتخاب نشده است.");
      return uploadBatch({ file, academic_year_label: academicYear, notes });
    },
    onSuccess: (created) => {
      setBatch(created);
      if (created.selected_sheet) {
        setSelectedSheet(created.selected_sheet);
      } else if (created.workbook_sheets.length === 1) {
        setSelectedSheet(created.workbook_sheets[0].name);
      }
      qc.invalidateQueries({ queryKey: ["batches"] });
      setStep(1);
    },
  });

  const sheetMutation = useMutation({
    mutationFn: (name: string) => selectSheet(batch!.id, name),
    onSuccess: (updated) => {
      setBatch(updated);
      setHeaderRow(1);
      setColumns([]);
    },
  });

  const headerMutation = useMutation({
    mutationFn: (row: number) => selectHeader(batch!.id, row),
    onSuccess: (updated) => {
      setBatch(updated);
      setColumns(updated.detected_columns);
      setStep(2);
    },
  });

  function validateFile(f: File): string | null {
    if (!f.name.toLowerCase().endsWith(".xlsx")) {
      return "فقط فایل‌های .xlsx پذیرفته می‌شوند.";
    }
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      return `حجم فایل نباید بیشتر از ${MAX_FILE_MB} مگابایت باشد.`;
    }
    return null;
  }

  function onFileChange(f: File | null) {
    setFileError(null);
    if (!f) {
      setFile(null);
      return;
    }
    const err = validateFile(f);
    if (err) {
      setFileError(err);
      setFile(null);
      return;
    }
    setFile(f);
  }

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Button variant="ghost" asChild className="mb-4 -mr-3">
        <button onClick={() => navigate("/batches")}>
          <ArrowLeft className="h-4 w-4" /> بازگشت به فهرست Batchها
        </button>
      </Button>

      <h1 className="mb-6 text-2xl font-bold">آپلود فایل ثبت‌نام</h1>

      <Stepper currentStep={step} steps={STEPS} />

      <Card className="mt-6">
        <CardContent className="p-6">
          {step === 0 && (
            <StepFile
              file={file}
              fileError={fileError}
              onFileChange={onFileChange}
              academicYear={academicYear}
              setAcademicYear={setAcademicYear}
              notes={notes}
              setNotes={setNotes}
              loading={uploadMutation.isPending}
              error={uploadMutation.error as Error | null}
              onSubmit={() => uploadMutation.mutate()}
            />
          )}

          {step === 1 && batch && (
            <StepSheetHeader
              batch={batch}
              selectedSheet={selectedSheet}
              headerRow={headerRow}
              setHeaderRow={setHeaderRow}
              onSelectSheet={(name) => {
                setSelectedSheet(name);
                sheetMutation.mutate(name);
              }}
              onInspect={() => headerMutation.mutate(headerRow)}
              loading={sheetMutation.isPending || headerMutation.isPending}
              error={sheetMutation.error || headerMutation.error}
              canProceed={Boolean(selectedSheet)}
            />
          )}

          {step === 2 && batch && (
            <StepReviewColumns
              batch={batch}
              columns={columns}
              onNext={() => navigate(`/batches/${batch.id}`)}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Stepper({ currentStep, steps }: { currentStep: number; steps: string[] }) {
  return (
    <ol className="flex items-center gap-2">
      {steps.map((label, i) => {
        const done = i < currentStep;
        const active = i === currentStep;
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
                done && "bg-emerald-600 text-white",
                active && "bg-primary text-white",
                !done && !active && "bg-slate-200 text-slate-600",
              )}
            >
              {done ? <CheckCircle2 className="h-5 w-5" /> : toPersianDigits(i + 1)}
            </span>
            <span
              className={cn(
                "text-sm",
                active ? "font-semibold text-slate-900" : "text-slate-500",
              )}
            >
              {label}
            </span>
            {i < steps.length - 1 && <span className="mx-2 h-px flex-1 bg-slate-200" />}
          </li>
        );
      })}
    </ol>
  );
}

interface StepFileProps {
  file: File | null;
  fileError: string | null;
  onFileChange: (f: File | null) => void;
  academicYear: string;
  setAcademicYear: (v: string) => void;
  notes: string;
  setNotes: (v: string) => void;
  loading: boolean;
  error: Error | null;
  onSubmit: () => void;
}

function StepFile({
  file, fileError, onFileChange,
  academicYear, setAcademicYear, notes, setNotes,
  loading, error, onSubmit,
}: StepFileProps) {
  const yearValid = /^\d{4}-\d{4}$/.test(academicYear);
  return (
    <div className="space-y-6">
      <div>
        <Label htmlFor="file">فایل Excel (فقط .xlsx — حداکثر ۱۰ مگابایت)</Label>
        <label
          htmlFor="file"
          className="mt-2 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center hover:border-primary hover:bg-primary/5"
        >
          {file ? (
            <>
              <FileSpreadsheet className="h-10 w-10 text-primary" />
              <p className="mt-3 font-medium text-slate-800">{file.name}</p>
              <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
            </>
          ) : (
            <>
              <UploadIcon className="h-10 w-10 text-slate-400" />
              <p className="mt-3 text-sm text-slate-600">
                برای انتخاب فایل کلیک کنید یا فایل را اینجا بکشید
              </p>
            </>
          )}
          <input
            id="file"
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />
        </label>
        {fileError && <p className="mt-2 text-xs text-red-600">{fileError}</p>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="year">سال تحصیلی (مثلاً ۱۴۰۵-۱۴۰۶)</Label>
          <Input
            id="year"
            value={academicYear}
            onChange={(e) => setAcademicYear(e.target.value)}
            placeholder="1405-1406"
            className="mt-1 tnum"
            dir="ltr"
          />
          {!yearValid && (
            <p className="mt-1 text-xs text-amber-600">
              فرمت باید چهار رقم، خط تیره، چهار رقم باشد.
            </p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="notes">یادداشت (اختیاری)</Label>
        <Textarea
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="مثلاً: این فایل نسخه‌ی اصلاح‌شده‌ی تاریخ ۱۴۰۵/۰۶/۱۰ است."
          className="mt-1"
        />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>آپلود ناموفق بود</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end">
        <Button onClick={onSubmit} disabled={!file || !yearValid || loading}>
          {loading ? <Spinner /> : <ArrowRight className="h-4 w-4" />}
          بارگذاری و ادامه
        </Button>
      </div>
    </div>
  );
}

interface StepSheetHeaderProps {
  batch: ImportBatch;
  selectedSheet: string;
  headerRow: number;
  setHeaderRow: (n: number) => void;
  onSelectSheet: (name: string) => void;
  onInspect: () => void;
  loading: boolean;
  error: Error | null;
  canProceed: boolean;
}

function StepSheetHeader({
  batch, selectedSheet, headerRow, setHeaderRow,
  onSelectSheet, onInspect, loading, error, canProceed,
}: StepSheetHeaderProps) {
  const sheets: SheetInfo[] = batch.workbook_sheets;
  return (
    <div className="space-y-6">
      <div>
        <Label>برگه (Sheet) را انتخاب کنید</Label>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {sheets.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => onSelectSheet(s.name)}
              className={cn(
                "rounded-lg border p-3 text-right transition",
                selectedSheet === s.name
                  ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                  : "border-slate-200 hover:border-slate-300",
              )}
            >
              <p className="font-medium text-slate-800">{s.name}</p>
              <p className="text-xs text-slate-500 tnum">
                {toPersianDigits(s.max_row)} سطر × {toPersianDigits(s.max_column)} ستون
              </p>
            </button>
          ))}
        </div>
      </div>

      {selectedSheet && (
        <div>
          <Label htmlFor="header-row">ردیف عنوان ستون‌ها (Header) چند است؟</Label>
          <p className="mb-2 text-xs text-slate-500">
            معمولاً ردیف ۱ است؛ اما اگر فایل شما چند ردیف توضیح در ابتدا دارد، شماره‌ی درست را وارد کنید.
          </p>
          <Input
            id="header-row"
            type="number"
            min={1}
            max={20}
            value={headerRow}
            onChange={(e) => setHeaderRow(Number(e.target.value))}
            className="w-32 tnum"
            dir="ltr"
          />
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>خطا</AlertTitle>
          <AlertDescription>{(error as Error).message}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end gap-2">
        <Button onClick={onInspect} disabled={!canProceed || loading}>
          {loading ? <Spinner /> : <ArrowRight className="h-4 w-4" />}
          مشاهده‌ی ستون‌ها
        </Button>
      </div>
    </div>
  );
}

function StepReviewColumns({
  batch,
  columns,
  onNext,
}: {
  batch: ImportBatch;
  columns: ColumnInfo[];
  onNext: () => void;
}) {
  const duplicateLabels = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of columns) counts[c.label] = (counts[c.label] ?? 0) + 1;
    return new Set(Object.keys(counts).filter((k) => counts[k] > 1));
  }, [columns]);

  return (
    <div className="space-y-6">
      <Alert variant="warning">
        <AlertTitle>آماده برای مرحله‌ی نگاشت</AlertTitle>
        <AlertDescription>
          فایل «{batch.original_filename}» بارگذاری شد و برگه‌ی «{batch.selected_sheet}» با
          {" "}
          <strong>{toPersianDigits(columns.length)}</strong> ستون شناسایی شد. در گام بعد هر
          ستون را به فیلد استاندارد نگاشت می‌کنید (ستون‌های تکراری با شماره موقعیت تفکیک می‌شوند).
        </AlertDescription>
      </Alert>

      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 text-right font-medium">ستون</th>
              <th className="px-3 py-2 text-right font-medium">عنوان</th>
              <th className="px-3 py-2 text-right font-medium">نمونه مقادیر</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((c) => (
              <tr key={c.index} className="border-t">
                <td className="px-3 py-2 tnum text-slate-500">{c.letter}</td>
                <td className="px-3 py-2 font-medium">
                  {c.label}
                  {duplicateLabels.has(c.label) && (
                    <span className="mr-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-800">
                      تکراری — موقعیت {c.letter}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-slate-500">
                  {c.samples.slice(0, 3).map((s) => (
                    <span
                      key={s}
                      className="ml-2 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs"
                    >
                      {s}
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end">
        <Button onClick={onNext}>
          ادامه به نگاشت <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
