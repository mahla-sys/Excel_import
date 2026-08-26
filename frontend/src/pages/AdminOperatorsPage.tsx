import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import {
  createOperator,
  createSchool,
  listOperators,
  listSchools,
} from "@/api/intake";
import { toPersianDigits } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function AdminOperatorsPage() {
  const qc = useQueryClient();
  const schoolsQ = useQuery({ queryKey: ["admin-schools"], queryFn: listSchools });
  const opsQ = useQuery({ queryKey: ["admin-operators"], queryFn: () => listOperators() });
  const [schoolDialog, setSchoolDialog] = useState(false);
  const [opDialog, setOpDialog] = useState(false);

  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ShieldAlert className="h-6 w-6 text-primary" />
            مدیریت مدرسه‌ها و اپراتورها
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            فقط برای مدیر فنی سامانه. اپراتورها فقط به داده‌ی مدرسه‌ی خود دسترسی دارند.
          </p>
        </div>
      </header>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">مدرسه‌ها</CardTitle>
            <Button size="sm" variant="outline" onClick={() => setSchoolDialog(true)}>
              <Plus className="h-4 w-4" /> مدرسه‌ی جدید
            </Button>
          </CardHeader>
          <CardContent>
            {schoolsQ.isLoading ? (
              <Spinner />
            ) : (
              <ul className="divide-y rounded-md border">
                {schoolsQ.data?.map((s) => (
                  <li key={s.id} className="flex items-center justify-between px-4 py-2">
                    <div>
                      <p className="text-sm font-medium">{s.name}</p>
                      <p className="font-mono text-xs text-slate-500" dir="ltr">
                        {s.external_code}
                      </p>
                    </div>
                    <Badge variant={s.is_active ? "success" : "secondary"}>
                      {s.is_active ? "فعال" : "غیرفعال"}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">اپراتورها</CardTitle>
            <Button size="sm" onClick={() => setOpDialog(true)}>
              <Plus className="h-4 w-4" /> اپراتور جدید
            </Button>
          </CardHeader>
          <CardContent>
            {opsQ.isLoading ? (
              <Spinner />
            ) : (
              <ul className="divide-y rounded-md border">
                {opsQ.data?.map((o) => (
                  <li key={o.id} className="flex items-center justify-between px-4 py-2">
                    <div>
                      <p className="text-sm font-medium">{o.username}</p>
                      <p className="text-xs text-slate-500">{o.school_name}</p>
                    </div>
                    <Badge variant={o.is_active ? "success" : "secondary"}>
                      {o.is_active ? "فعال" : "غیرفعال"}
                    </Badge>
                  </li>
                ))}
                {opsQ.data?.length === 0 && (
                  <li className="px-4 py-6 text-center text-sm text-slate-500">
                    هنوز اپراتوری ساخته نشده.
                  </li>
                )}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <CreateSchoolDialog
        open={schoolDialog}
        onOpenChange={setSchoolDialog}
        onCreated={() => qc.invalidateQueries({ queryKey: ["admin-schools"] })}
      />
      <CreateOperatorDialog
        open={opDialog}
        onOpenChange={setOpDialog}
        schools={schoolsQ.data ?? []}
        onCreated={() => qc.invalidateQueries({ queryKey: ["admin-operators"] })}
      />
    </div>
  );
}

function CreateSchoolDialog({
  open, onOpenChange, onCreated,
}: { open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mut = useMutation({
    mutationFn: () => createSchool({ name, external_code: code }),
    onSuccess: () => {
      setName("");
      setCode("");
      onCreated();
      onOpenChange(false);
    },
    onError: (e: Error) => setError(e.message),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>مدرسه‌ی جدید</DialogTitle>
          <DialogDescription>
            شناسه‌ی خارجی پایدار باید یکتا باشد و در سیستم اصلی هم استفاده خواهد شد.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>نام مدرسه</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label>کد خارجی (external_code)</Label>
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="مثلاً SCHOOL-03"
              dir="ltr"
            />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>انصراف</Button>
          <Button
            onClick={() => mut.mutate()}
            disabled={!name || !code || mut.isPending}
          >
            {mut.isPending ? <Spinner /> : "ساخت"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CreateOperatorDialog({
  open, onOpenChange, schools, onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  schools: { id: number; name: string }[];
  onCreated: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [schoolId, setSchoolId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const mut = useMutation({
    mutationFn: () =>
      createOperator({
        username,
        password,
        school_tenant: Number(schoolId),
      }),
    onSuccess: () => {
      setUsername("");
      setPassword("");
      setSchoolId("");
      onCreated();
      onOpenChange(false);
    },
    onError: (e: Error) => setError(e.message),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>اپراتور جدید</DialogTitle>
          <DialogDescription>
            رمز باید حداقل ۱۰ کاراکتر باشد و در اولین ورود به‌صورت امن به اپراتور تحویل داده شود.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>نام کاربری</Label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} dir="ltr" />
          </div>
          <div>
            <Label>رمز عبور</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              dir="ltr"
            />
          </div>
          <div>
            <Label>مدرسه</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={schoolId}
              onChange={(e) => setSchoolId(Number(e.target.value))}
            >
              <option value="">— انتخاب کنید —</option>
              {schools.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>انصراف</Button>
          <Button
            onClick={() => mut.mutate()}
            disabled={!username || password.length < 10 || !schoolId || mut.isPending}
          >
            {mut.isPending ? <Spinner /> : "ساخت اپراتور"}
          </Button>
        </DialogFooter>
        <p className="text-xs text-slate-400">تعداد اپراتورها: {toPersianDigits(schools.length)} مدرسه</p>
      </DialogContent>
    </Dialog>
  );
}
