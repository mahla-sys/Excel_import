import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { apiRequest } from "@/api/client";

interface Props {
  /** When true, the dialog cannot be dismissed (forced first-login flow). */
  forced?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChangePasswordDialog({ forced = false, open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      apiRequest("/auth/change-password/", {
        method: "POST",
        body: { current_password: current, new_password: next },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      setCurrent("");
      setNext("");
      setConfirm("");
      onOpenChange(false);
    },
    onError: (e: Error) => {
      // The backend may return field-level errors; show a generic message.
      setError(e.message || "تغییر رمز ناموفق بود.");
    },
  });

  const mismatched = confirm.length > 0 && next !== confirm;
  const canSubmit =
    current.length > 0 &&
    next.length >= 10 &&
    next === confirm &&
    !mutation.isPending;

  function submit() {
    setError(null);
    mutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !forced && onOpenChange(o)}>
      <DialogContent className="max-w-md" showCloseButton={!forced}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-primary" />
            {forced ? "تغییر رمز عبور الزامی است" : "تغییر رمز عبور"}
          </DialogTitle>
          <DialogDescription>
            {forced
              ? "رمز عبور شما موقت است. پیش از ادامه، لطفاً یک رمز جدید حداقل ۱۰ کاراکتری انتخاب کنید."
              : "رمز جدید باید حداقل ۱۰ کاراکتر باشد."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label htmlFor="cur">رمز فعلی</Label>
            <Input
              id="cur"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              dir="ltr"
              autoComplete="current-password"
            />
          </div>
          <div>
            <Label htmlFor="next">رمز جدید</Label>
            <Input
              id="next"
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              dir="ltr"
              autoComplete="new-password"
            />
          </div>
          <div>
            <Label htmlFor="confirm">تکرار رمز جدید</Label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              dir="ltr"
              autoComplete="new-password"
            />
            {mismatched && (
              <p className="mt-1 text-xs text-red-600">تکرار رمز مطابقت ندارد.</p>
            )}
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          {!forced && (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              انصراف
            </Button>
          )}
          <Button onClick={submit} disabled={!canSubmit}>
            {mutation.isPending ? <Spinner /> : null}
            ذخیره رمز جدید
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
