import { apiRequest, apiDownload } from "./client";

export type BatchStatus =
  | "uploaded"
  | "mapping_required"
  | "processing"
  | "review_required"
  | "validated"
  | "approved_by_school"
  | "ready_for_future_integration"
  | "failed"
  | "archived";

export interface SheetInfo {
  name: string;
  max_row: number;
  max_column: number;
}

export interface ColumnInfo {
  index: number;
  letter: string;
  label: string;
  samples: string[];
}

export interface MappingTarget {
  source_column_index: number;
  source_column_label?: string;
}

export type Mapping = Record<string, MappingTarget>;

export interface UnknownColumn {
  index: number;
  label: string;
  action: "extra_attribute" | "ignored" | "requires_decision";
}

export interface MappingSnapshot {
  mappings: Mapping;
  unknown_columns: UnknownColumn[];
  saved_at: string;
  profile_id: number | null;
  profile_version: number | null;
}

export interface ImportBatch {
  id: number;
  school: number;
  school_name?: string;
  uploaded_by_username?: string;
  original_filename: string;
  academic_year_label: string;
  status: BatchStatus;
  status_display: string;
  selected_sheet: string;
  header_row_number: number | null;
  file_size: number;
  workbook_sheets: SheetInfo[];
  detected_columns: ColumnInfo[];
  mapping_profile: number | null;
  mapping_snapshot: MappingSnapshot | null;
  failure_reason: string;
  stats: Record<string, number>;
  uploaded_at: string;
  processed_at: string | null;
  reviewed_at: string | null;
  approved_at: string | null;
}

export interface CanonicalField {
  path: string;
  label: string;
}

export interface CanonicalFieldGroup {
  id: string;
  label: string;
  fields: string[];
}

export interface Suggestion {
  column_index: number;
  column_label: string;
  target: string | null;
  target_label: string | null;
  confidence: "high" | "medium" | "low" | "none";
  reason: string;
  alternatives: { path: string; label: string }[];
}

export interface MappingProfile {
  id: number;
  name: string;
  version: number;
  is_active: boolean;
  mappings: Mapping;
  unknown_columns: UnknownColumn[];
  sheet_name_hint: string;
  header_row_hint: number | null;
  created_at: string;
  updated_at: string;
}

export const BatchStatusLabels: Record<BatchStatus, string> = {
  uploaded: "آپلود شد",
  mapping_required: "نیازمند نگاشت",
  processing: "در حال پردازش",
  review_required: "نیازمند بررسی",
  validated: "اعتبارسنجی شد",
  approved_by_school: "تأیید مدرسه",
  ready_for_future_integration: "آماده انتقال آینده",
  failed: "ناموفق",
  archived: "بایگانی شد",
};

// --- API functions -------------------------------------------------------

export function listBatches(): Promise<ImportBatch[]> {
  return apiRequest<ImportBatch[]>("/intake/batches/");
}

export function getBatch(id: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/`);
}

export function uploadBatch(payload: {
  file: File;
  academic_year_label: string;
  notes?: string;
}): Promise<ImportBatch> {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("academic_year_label", payload.academic_year_label);
  if (payload.notes) form.append("notes", payload.notes);
  return apiRequest<ImportBatch>("/intake/batches/upload/", {
    method: "POST",
    body: form,
  });
}

export function selectSheet(id: number, sheet_name: string): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/select-sheet/`, {
    method: "POST",
    body: { sheet_name },
  });
}

export function selectHeader(id: number, header_row: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/select-header/`, {
    method: "POST",
    body: { header_row },
  });
}

export function fetchSuggestions(batchId: number): Promise<{ suggestions: Suggestion[] }> {
  return apiRequest(`/intake/batches/${batchId}/mapping/suggestions/`);
}

export function fetchCanonicalFields(): Promise<{
  fields: CanonicalField[];
  groups: CanonicalFieldGroup[];
}> {
  return apiRequest("/intake/canonical-fields/");
}

export function listMappingProfiles(): Promise<MappingProfile[]> {
  return apiRequest("/intake/mapping-profiles/");
}

export interface SaveMappingPayload {
  mappings?: Mapping;
  unknown_columns?: UnknownColumn[];
  save_as_profile?: string;
  profile_id?: number;
  accept_suggestions?: boolean;
}

export function saveBatchMapping(
  batchId: number,
  payload: SaveMappingPayload,
): Promise<ImportBatch & { consistency_warnings?: string[] }> {
  return apiRequest(`/intake/batches/${batchId}/mapping/`, {
    method: "POST",
    body: payload,
  });
}

export function archiveBatch(id: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/archive/`, {
    method: "POST",
  });
}

export function processBatch(id: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/process/`, {
    method: "POST",
  });
}

export interface StagedGuardian {
  id: number;
  relation_type: "father" | "mother" | "other";
  relation_display: string;
  first_name: string;
  last_name: string;
  full_name: string;
  national_id: string;
  mobile: string;
  occupation: string;
  education_level: string;
}

export interface StagedStudent {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  national_id: string;
  national_id_valid: boolean | null;
  source_student_code: string;
  grade: string;
  classroom_title: string;
  placement_status: "pending" | "placed";
  admission_status: string;
  gender: string;
  status: string;
  guardians: StagedGuardian[];
}

export function listStagedStudents(
  batchId: number,
  status?: string,
): Promise<StagedStudent[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiRequest(`/intake/batches/${batchId}/students/${qs}`);
}

export function revalidateBatch(id: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/revalidate/`, { method: "POST" });
}

export function approveBatch(id: number): Promise<ImportBatch> {
  return apiRequest<ImportBatch>(`/intake/batches/${id}/approve/`, { method: "POST" });
}

export function getStudent(id: number): Promise<StagedStudent & {
  validation_issues: { code: string; severity: string; field?: string; message: string; other_student_ids?: number[] }[];
  field_provenance: Record<string, {
    raw_value?: string;
    normalized_value?: string;
    column_label?: string;
    last_edited_by?: string;
    last_edited_at?: string;
    edit_reason?: string;
  }>;
  contacts: { emergency_mobile?: string; student_mobile?: string; home_phone?: string };
  admission_data: Record<string, unknown>;
  extra_attributes: Record<string, unknown>;
  birth_date: string | null;
  review_notes: string;
  duplicate_resolutions: {
    id: number;
    issue_code: string;
    decision: string;
    review_note: string;
    reviewer_username: string;
    created_at: string;
  }[];
}> {
  return apiRequest(`/intake/students/${id}/`);
}

export interface StudentPatchPayload {
  first_name?: string;
  last_name?: string;
  national_id?: string;
  source_student_code?: string;
  birth_date?: string;
  gender?: string;
  grade?: string;
  classroom_title?: string;
  emergency_mobile?: string;
  review_notes?: string;
  edit_reason?: string;
}

export function patchStudent(id: number, payload: StudentPatchPayload): Promise<unknown> {
  return apiRequest(`/intake/students/${id}/`, { method: "PATCH", body: payload });
}

export type DuplicateDecision =
  | "confirmed_duplicate"
  | "confirmed_distinct_people"
  | "corrected_source_data"
  | "needs_follow_up";

export function resolveStudent(
  id: number,
  payload: { issue_code: string; decision: DuplicateDecision; review_note: string },
): Promise<unknown> {
  return apiRequest(`/intake/students/${id}/resolve/`, { method: "POST", body: payload });
}

export function downloadOriginalFile(id: number): Promise<Response> {
  return apiDownload(`/intake/batches/${id}/original-file/`);
}

/** Trigger a browser download from a fetch Response. */
async function saveResponse(resp: Response, fallbackName: string) {
  if (!resp.ok) throw new Error("دانلود ناموفق بود.");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  // Prefer server-provided filename if present.
  const cd = resp.headers.get("Content-Disposition") || "";
  const match = /filename\*=UTF-8''([^;]+)/.exec(cd) || /filename="([^"]+)"/.exec(cd);
  a.download = match ? decodeURIComponent(match[1]) : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadErrorReport(batchId: number) {
  return apiDownload(`/intake/batches/${batchId}/export/errors/`).then((r) =>
    saveResponse(r, `batch-${batchId}-errors.xlsx`),
  );
}

export function downloadCanonicalXlsx(batchId: number) {
  return apiDownload(`/intake/batches/${batchId}/export/canonical/xlsx/`).then((r) =>
    saveResponse(r, `batch-${batchId}-canonical.xlsx`),
  );
}

export function downloadCanonicalJson(batchId: number) {
  return apiDownload(`/intake/batches/${batchId}/export/canonical/json/`).then((r) =>
    saveResponse(r, `batch-${batchId}-canonical.json`),
  );
}

// Dashboard / admin --------------------------------------------------------

export interface DashboardStats {
  school: { id: number; name: string; external_code: string } | null;
  totals: { batches: number; students: number; approved_batches: number };
  batch_status_counts: Record<string, number>;
  student_status_counts: Record<string, number>;
  recent_batches: {
    id: number;
    original_filename: string;
    academic_year_label: string;
    status: string;
    uploaded_at: string;
  }[];
}

export function fetchDashboard(): Promise<DashboardStats> {
  return apiRequest("/dashboard/");
}

export interface AdminSchool {
  id: number;
  name: string;
  external_code: string;
  is_active: boolean;
  created_at: string;
}

export function listSchools(): Promise<AdminSchool[]> {
  return apiRequest("/admin/schools/");
}

export function createSchool(payload: { name: string; external_code: string }) {
  return apiRequest<AdminSchool>("/admin/schools/", { method: "POST", body: payload });
}

export interface AdminOperator {
  id: number;
  username: string;
  school_tenant: number;
  school_name: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export function listOperators(schoolId?: number): Promise<AdminOperator[]> {
  const qs = schoolId ? `?school=${schoolId}` : "";
  return apiRequest(`/admin/operators/${qs}`);
}

export function createOperator(payload: {
  username: string;
  password: string;
  school_tenant: number;
}) {
  return apiRequest<AdminOperator>("/admin/operators/", { method: "POST", body: payload });
}

export interface AuditEntry {
  id: number;
  actor_username: string;
  action: string;
  entity_type: string;
  entity_id: string;
  school_name: string;
  before_state: unknown;
  after_state: unknown;
  ip_address: string | null;
  created_at: string;
}

export function listAuditLog(params?: {
  action?: string;
  entity_type?: string;
  school?: string;
}): Promise<AuditEntry[]> {
  const qs = new URLSearchParams(
    Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== "") as string[][],
  ).toString();
  return apiRequest(`/admin/audit-log/${qs ? `?${qs}` : ""}`);
}
