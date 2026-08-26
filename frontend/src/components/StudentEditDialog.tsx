import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getStudent, patchStudent, type StudentPatchPayload } from "@/api/intake";
import { toPersianDigits } from "@/lib/utils";

interface Props {
  studentId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const GENDERS = [
  { value: "", label: "—" },
  { value: "male", label: "پسر" },
  { value: "female", label: "دختر" },
];

const GRADES = [
  "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم",
  "هفتم", "هشتم", "نهم", "دهم", "یازدهم", "دوازدهم",
];

const SENSITIVE = new Set([
  "first_name",
  "last_name",
  "national_id",
  "birth_date",
  "gender",
  "grade",
  "emergency_mobile",
]);

export function StudentEditDialog({ studentId, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const studentQuery = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => getStudent(studentId!),
    enabled: open && studentId != null,
  });

  const [form, setForm] = useState<StudentPatchPayload>({});

  useEffect(() => {
    if (studentQuery.data) {
      const s = studentQuery.data;
      setForm({
        first_name: s.first_name,
        last_name: s.last_name,
        national_id: s.national_id,
        source_student_code: s.source_student_code,
        birth_date: s.birth_date ?? "",
        gender: s.gender,
        grade: s.grade,
        classroom_title: s.classroom_title,
        emergency_mobile: s.contacts?.emergency_mobile ?? "",
        review_notes: s.review_notes,
      });
    }
  }, [studentQuery.data]);

  if (studentQuery.isLoading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <div className="flex items-center gap-2 text-slate-500">
            <Spinner /> در حال بارگذاری پرونده…
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const s = studentQuery.data;
  if (!s) return null;

  const provenance = s.field_provenance ?? {};

  const changedFields = new Set(Object.keys(form).filter((k) => {
    if (k === "emergency_mobile") {
      const cur = (s.contacts as { emergency_mobile?: string })?.emergency_mobile ?? "";
      return (form.emergency_mobile ?? "") !== cur;
    }
    return form[k as keyof StudentPatchPayload]?.toString() !== (s[k as keyof typeof s] ?? "")?.toString();
  }));

  const needsReason = [...changedFields].some((f) => SENSITIVE.has(f));
  const reasonMissing = needsReason && !(form.edit_reason?.trim() ?? "");

  const mutation = useMutation({
    mutationFn: () => patchStudent(studentId!, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batch-students"] });
      qc.invalidateQueries({ queryKey: ["batch"] });
      onOpenChange(false);
    },
  });

  const set = <K extends keyof StudentPatchPayload>(k: K, v: StudentPatchPayload[K]) => {
    setForm((prev) => ({ ...prev, [k]: v }));
  };

  const blockingIssues = (s.validation_issues ?? []).filter((i) => i.severity === "error");
  const warnings = (s.validation_issues ?? []).filter((i) => i.severity === "warning");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>ویرایش پرونده‌ی دانش‌آموز</DialogTitle>
          <DialogDescription>
            مقدار خام اولیه از اکسل پاک نمی‌شود؛ هر تغییر با نام شما و دلیل ثبت می‌گردد.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <FieldWithProvenance
            label="نام"
            provenance={provenance["student.first_name"]}
            normalizedValue={s.first_name}
          >
            <Input value={form.first_name ?? ""} onChange={(e) => set("first_name", e.target.value)} />
          </FieldWithProvenance>
          <FieldWithProvenance
            label="نام خانوادگی"
            provenance={provenance["student.last_name"]}
            normalizedValue={s.last_name}
          >
            <Input value={form.last_name ?? ""} onChange={(e) => set("last_name", e.target.value)} />
          </FieldWithProvenance>
          <FieldWithProvenance
            label="کد ملی"
            hint="در این صفحه به‌صورت کامل (فقط برای کاربر مجاز) نمایش داده می‌شود."
            provenance={provenance["student.national_id"]}
            normalizedValue={s.national_id}
            sensitive
          >
            <Input
              value={form.national_id ?? ""}
              onChange={(e) => set("national_id", e.target.value)}
              dir="ltr"
              className="tnum text-left"
            />
          </FieldWithProvenance>
          <FieldWithProvenance
            label="کد پرونده / کد دانش‌آموزی (اختیاری)"
            provenance={provenance["student.source_student_code"]}
            normalizedValue={s.source_student_code}
          >
            <Input
              value={form.source_student_code ?? ""}
              onChange={(e) => set("source_student_code", e.target.value)}
            />
          </FieldWithProvenance>
          <FieldWithProvenance
            label="تاریخ تولد"
            hint="به‌صورت ISO مثل 2001-09-05"
            provenance={provenance["student.birth_date"]}
            normalizedValue={s.birth_date ?? ""}
          >
            <Input
              value={form.birth_date ?? ""}
              onChange={(e) => set("birth_date", e.target.value)}
              dir="ltr"
              className="tnum text-left"
            />
          </FieldWithProvenance>
          <Field label="جنسیت">
            <select
              value={form.gender ?? ""}
              onChange={(e) => set("gender", e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {GENDERS.map((g) => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
          </Field>
          <Field label="پایه">
            <select
              value={form.grade ?? ""}
              onChange={(e) => set("grade", e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">—</option>
              {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </Field>
          <Field label="کلاس/شعبه (اختیاری)">
            <Input
              value={form.classroom_title ?? ""}
              onChange={(e) => set("classroom_title", e.target.value)}
            />
          </Field>
          <FieldWithProvenance
            label="شماره تماس ضروری"
            hint="فرمت: 09xxxxxxxxx"
            provenance={provenance["contacts.emergency_mobile"]}
            normalizedValue={s.contacts?.emergency_mobile ?? ""}
          >
            <Input
              value={form.emergency_mobile ?? ""}
              onChange={(e) => set("emergency_mobile", e.target.value)}
              dir="ltr"
              className="tnum text-left"
            />
          </FieldWithProvenance>
        </div>

        <div>
          <Label htmlFor="review-notes" className="mb-1 block">یادداشت بررسی</Label>
          <Textarea
            id="review-notes"
            value={form.review_notes ?? ""}
            onChange={(e) => set("review_notes", e.target.value)}
            placeholder="توضیحات تکمیلی برای ثبت در پرونده"
          />
        </div>

        {needsReason && (
          <div>
            <Label htmlFor="edit-reason" className="mb-1 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
              دلیل اصلاح فیلدهای حساس (الزامی)
            </Label>
            <Input
              id="edit-reason"
              value={form.edit_reason ?? ""}
              onChange={(e) => set("edit_reason", e.target.value)}
              placeholder="مثلاً: اصلاح کد ملی بر اساس شناسنامه دانش‌آموز"
            />
          </div>
        )}

        {blockingIssues.length > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>خطاهای مسدودکننده</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 list-disc pr-5 text-xs">
                {blockingIssues.map((i, idx) => (
                  <li key={idx}>{i.message || i.code}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
        {warnings.length > 0 && (
          <Alert variant="warning">
            <AlertTitle>هشدارها</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 list-disc pr-5 text-xs">
                {warnings.slice(0, 4).map((i, idx) => (
                  <li key={idx}>{i.message || i.code}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            انصراف
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || reasonMissing || changedFields.size === 0}
          >
            {mutation.isPending ? <Spinner /> : <Save className="h-4 w-4" />}
            ذخیره و اعتبارسنجی مجدد
          </Button>
        </DialogFooter>

        {mutation.error && (
          <p className="text-xs text-red-600">{(mutation.error as Error).message}</p>
        )}
        {changedFields.size > 0 && (
          <p className="text-xs text-slate-400">
            {toPersianDigits(changedFields.size)} فیلد تغییر کرده
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <Label className="mb-1 block">{label}</Label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}

type ProvenanceEntry = {
  raw_value?: string;
  normalized_value?: string;
  last_edited_by?: string;
  last_edited_at?: string;
  edit_reason?: string;
  column_label?: string;
};

function FieldWithProvenance({
  label,
  hint,
  children,
  provenance,
  normalizedValue,
  sensitive,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  provenance?: ProvenanceEntry;
  normalizedValue?: string;
  sensitive?: boolean;
}) {
  const raw = provenance?.raw_value ?? "";
  const norm = normalizedValue ?? "";
  // Show "raw value from Excel" only when present and different from the
  // current normalized value (keeps the UI compact).
  const showRaw =
    raw !== "" && raw !== norm && raw !== (provenance?.normalized_value ?? "");
  const edited = provenance?.last_edited_by
    ? `${provenance.last_edited_by} — ${new Date(provenance.last_edited_at!).toLocaleString("fa-IR")}`
    : null;
  return (
    <div>
      <Label className="mb-1 flex items-center gap-1">
        {label}
        {sensitive && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800">
            حساس
          </span>
        )}
      </Label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-slate-400">{hint}</p>}
      {showRaw && (
        <p className="mt-1 text-[11px] text-slate-500">
          مقدار خام اکسل: <span dir="auto" className="font-mono text-slate-600">{raw}</span>
        </p>
      )}
      {edited && (
        <p className="mt-1 text-[11px] text-slate-400">
          آخرین ویرایش: {edited}
          {provenance?.edit_reason ? ` — دلیل: ${provenance.edit_reason}` : ""}
        </p>
      )}
    </div>
  );
}
