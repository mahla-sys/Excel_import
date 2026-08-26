import { useState } from "react";
import { useForm } from "react-hook-form";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

interface LoginForm {
  username: string;
  password: string;
}

export default function LoginPage() {
  const { login } = useAuth();
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ mode: "onTouched" });

  const onSubmit = async (data: LoginForm) => {
    setSubmissionError(null);
    try {
      await login(data.username.trim(), data.password);
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmissionError(err.message);
      } else {
        setSubmissionError("ورود ناموفق بود. لطفاً دوباره تلاش کنید.");
      }
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 to-brand-50 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-slate-900">
            پرتال مرکزی ورود داده مدارس
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            برای ورود، نام کاربری و رمز عبور مسئول مدرسه را وارد کنید.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="card space-y-4">
          <div>
            <label htmlFor="username" className="label">
              نام کاربری
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              className="input"
              {...register("username", { required: "نام کاربری الزامی است." })}
            />
            {errors.username && (
              <p className="mt-1 text-xs text-red-600">{errors.username.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="label">
              رمز عبور
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              className="input"
              {...register("password", { required: "رمز عبور الزامی است." })}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
            )}
          </div>

          {submissionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {submissionError}
            </div>
          )}

          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? "در حال ورود…" : "ورود"}
          </button>

          <p className="text-center text-xs text-slate-400">
            ثبت‌نام عمومی در این سامانه وجود ندارد.
          </p>
        </form>
      </div>
    </div>
  );
}
