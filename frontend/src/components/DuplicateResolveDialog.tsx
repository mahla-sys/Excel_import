import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getStudent, resolveStudent, type DuplicateDecision } from "@/api/intake";
import { cn, toPersianDigits } from "@/lib/utils";

interface Props {
  studentId: number | null;
  issueCode: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DECISIONS: { value: DuplicateDecision; label: string; hint: string }[] = [
  {
    value: "confirmed_duplicate",
    label: "تکرار تأیید شد",
    hint: "رکوردها در اصل یک دانش‌آموز هستند؛ در سیستم اصلی با هم ترکیب می‌شوند.",
  },
  {
    value: "confirmed_distinct_people",
    label: "افراد متفاوت هستند",
    hint: "اطلاعات شباهت اتفاقی است (مثلاً نام مشترک خانوادگی).",
  },
  {
    value: "corrected_source_data",
    label: "داده‌ی منبع اصلاح شد",
    hint: "خطای تکرار با ویرایش رکورد برطرف شده است.",
  },
  {
    value: "needs_follow_up",
    label: "نیازمند پیگیری",
    hint: "برای تصمیم قطعی باید با مدرسه/خانواده تماس گرفت.",
  },
];

export function DuplicateResolveDialog({ studentId, issueCode, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const student = useQuery({
    queryKey: ["student", studentId],
    queryFn: () => getStudent(studentId!),
    enabled: open && studentId != null,
  });

  const [decision, setDecision] = useState<DuplicateDecision | "">("");
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      resolveStudent(studentId!, {
        issue_code: issueCode!,
        decision: decision as DuplicateDecision,
        review_note: note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batch-students"] });
      qc.invalidateQueries({ queryKey: ["batch"] });
      onOpenChange(false);
    },
  });

  const issue = (student.data?.validation_issues ?? []).find(
    (i) => i.code === issueCode,
  );
  const alreadyResolved = (student.data?.duplicate_resolutions ?? []).some(
    (r) => r.issue_code === issueCode,
  );

  const canSave = decision !== "" && note.trim().length >= 3 && !mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        {student.isLoading ? (
          <div className="flex items-center gap-2 text-slate-500">
            <Spinner /> در حال بارگذاری…
          </div>
        ) : !student.data ? null : (
          <>
            <DialogHeader>
              <DialogTitle>رفع ابهام هویتی</DialogTitle>
              <DialogDescription>
                {student.data.full_name} — کد ملی:{" "}
                <span className="tnum font-mono" dir="ltr">
                  {student.data.national_id || "—"}
                </span>
              </DialogDescription>
            </DialogHeader>

            {issue && (
              <Alert variant="warning">
                <AlertTitle>{issue.code}</AlertTitle>
                <AlertDescription>{issue.message}</AlertDescription>
                {issue.other_student_ids && issue.other_student_ids.length > 0 && (
                  <p className="mt-2 text-xs text-slate-500">
                    شناسه‌ی رکوردهای مشابه:{" "}
                    {issue.other_student_ids.map(toPersianDigits).join("، ")}
                  </p>
                )}
              </Alert>
            )}

            {alreadyResolved ? (
              <Alert>
                <AlertTitle>قبلاً تصمیم‌گیری شده</AlertTitle>
                <AlertDescription>
                  این هشدار پیش‌تر توسط{" "}
                  <strong>{student.data.duplicate_resolutions[0].reviewer_username}</strong>{" "}
                  با وضعیت «{student.data.duplicate_resolutions[0].decision}» ثبت شده است.
                  می‌توانید با ثبت تصمیم جدید آن را به‌روزرسانی کنید.
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="space-y-2">
              <Label>تصمیم شما</Label>
              <div className="grid gap-2 sm:grid-cols-2">
                {DECISIONS.map((d) => (
                  <button
                    key={d.value}
                    type="button"
                    onClick={() => setDecision(d.value)}
                    className={cn(
                      "rounded-lg border p-3 text-right transition",
                      decision === d.value
                        ? "border-primary bg-primary/5 ring-2 ring-primary/30"
                        : "border-slate-200 hover:bg-slate-50",
                    )}
                  >
                    <div className="text-sm font-medium text-slate-800">{d.label}</div>
                    <div className="mt-1 text-xs text-slate-500">{d.hint}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label htmlFor="note" className="mb-1 block">
                توضیح بررسی (حداقل ۳ کاراکتر)
              </Label>
              <Textarea
                id="note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="مثلاً: با معاون مدرسه تماس گرفته شد؛ کد ملی متعلق به برادر دوقلو است."
              />
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                انصراف
              </Button>
              <Button onClick={() => mutation.mutate()} disabled={!canSave}>
                {mutation.isPending ? <Spinner /> : null}
                ثبت تصمیم
              </Button>
            </DialogFooter>

            {mutation.error && (
              <p className="text-xs text-red-600">
                {(mutation.error as Error).message}
              </p>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
