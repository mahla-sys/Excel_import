"""Controlled vocabularies and status enums for the intake pipeline."""
from django.db import models


class BatchStatus(models.TextChoices):
    UPLOADED = "uploaded", "آپلود شد"
    MAPPING_REQUIRED = "mapping_required", "نیازمند نگاشت"
    PROCESSING = "processing", "در حال پردازش"
    REVIEW_REQUIRED = "review_required", "نیازمند بررسی"
    VALIDATED = "validated", "اعتبارسنجی شد"
    APPROVED = "approved_by_school", "تأیید مدرسه"
    READY = "ready_for_future_integration", "آماده‌ی انتقال آینده"
    FAILED = "failed", "ناموفق"
    ARCHIVED = "archived", "بایگانی شد"


# Statuses in which a Batch is safe to re-process or edit.
EDITABLE_BATCH_STATUSES = {
    BatchStatus.UPLOADED,
    BatchStatus.MAPPING_REQUIRED,
    BatchStatus.REVIEW_REQUIRED,
    BatchStatus.VALIDATED,
}


class RowStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    NEEDS_REVIEW = "needs_review", "نیازمند بررسی"
    INCOMPLETE = "incomplete", "ناقص"
    VALIDATED = "validated", "معتبر"
    PENDING_PLACEMENT = "pending_placement", "در انتظار کلاس‌بندی"
    READY = "ready_for_future_integration", "آماده‌ی انتقال"
    ARCHIVED = "archived", "بایگانی شد"


class PlacementStatus(models.TextChoices):
    PENDING = "pending", "کلاس مشخص نشده"
    PLACED = "placed", "کلاس مشخص شده"


class AdmissionStatus(models.TextChoices):
    CONFIRMED = "confirmed", "قطعی"
    RESERVED = "reserved", "رزرو"
    CANCELLED = "cancelled", "لغو شده"


class IssueSeverity(models.TextChoices):
    ERROR = "error", "خطا"
    WARNING = "warning", "هشدار"
    INFO = "info", "اطلاع"


# Standardized issue codes.
class IssueCode:
    STUDENT_NAME_MISSING = "E-STUDENT-NAME-MISSING"
    NID_CHECKSUM = "E-NID-CHECKSUM"
    NID_LENGTH = "E-NID-LENGTH"
    NID_DIGITS = "E-NID-DIGITS"
    NID_MISSING = "W-NID-MISSING"
    GRADE_MISSING = "W-GRADE-MISSING"
    CLASSROOM_PENDING = "W-CLASSROOM-PENDING"
    EMERGENCY_CONTACT_MISSING = "W-EMERGENCY-CONTACT-MISSING"
    DUPLICATE_EXACT = "W-DUPLICATE-EXACT"
    DUPLICATE_SUSPECTED = "W-DUPLICATE-SUSPECTED"
    DOCUMENT_REFERENCE_UNVERIFIED = "W-DOCUMENT-REFERENCE-UNVERIFIED"
    BIRTHDATE_INVALID = "E-BIRTHDATE-INVALID"
    PHONE_INVALID = "W-PHONE-INVALID"
    GENDER_INVALID = "W-GENDER-INVALID"
    GRADE_UNKNOWN = "W-GRADE-UNKNOWN"
    NID_NONDIGIT = "W-NID-NONDIGIT"
    NID_PADDED = "W-NID-PADDED"
    ACADEMIC_YEAR_RANGE = "W-ACADEMIC-YEAR-RANGE"
    ROW_EMPTY = "E-ROW-EMPTY"
    ACADEMIC_YEAR_MISSING = "E-ACADEMIC-YEAR-MISSING"
    TOO_MANY_ROWS = "E-TOO-MANY-ROWS"
    FILE_TOO_LARGE = "E-FILE-TOO-LARGE"
    FILE_TYPE = "E-FILE-TYPE"
    UNKNOWN_COLUMN = "I-UNKNOWN-COLUMN"


# The full set of canonical field paths accepted by the mapper. Each path
# maps to a human-friendly Persian label used in the mapping UI.
CANONICAL_FIELDS = {
    # Identity
    "student.first_name": "نام دانش‌آموز",
    "student.last_name": "نام خانوادگی دانش‌آموز",
    "student.full_name": "نام کامل دانش‌آموز",
    "student.national_id": "کد ملی دانش‌آموز",
    "student.source_student_code": "کد پرونده/کد دانش‌آموزی",
    "student.birth_date": "تاریخ تولد",
    "student.gender": "جنسیت",
    "student.birth_place": "محل تولد",
    # Enrollment
    "enrollment.grade": "پایه",
    "enrollment.classroom_title": "عنوان کلاس/شعبه",
    "enrollment.admission_status": "وضعیت ثبت‌نام",
    # Contacts
    "contacts.student_mobile": "موبایل دانش‌آموز",
    "contacts.emergency_mobile": "شماره تماس ضروری",
    "contacts.emergency_contact_relation": "نسبت صاحب شماره ضروری",
    "contacts.home_phone": "تلفن ثابت",
    "contacts.home_address": "آدرس منزل",
    "contacts.postal_code": "کد پستی",
    "contacts.student_lives_with": "وضعیت زندگی دانش‌آموز",
    # Father
    "guardian.father.first_name": "نام پدر",
    "guardian.father.last_name": "نام خانوادگی پدر",
    "guardian.father.full_name": "نام و نام خانوادگی پدر",
    "guardian.father.national_id": "کد ملی پدر",
    "guardian.father.birth_date": "تاریخ تولد پدر",
    "guardian.father.mobile": "موبایل پدر",
    "guardian.father.education_level": "تحصیلات پدر",
    "guardian.father.field_of_study": "رشته تحصیلی پدر",
    "guardian.father.employment_status": "وضعیت اشتغال پدر",
    "guardian.father.occupation": "شغل پدر",
    "guardian.father.workplace_address": "آدرس محل کار پدر",
    # Mother
    "guardian.mother.first_name": "نام مادر",
    "guardian.mother.last_name": "نام خانوادگی مادر",
    "guardian.mother.full_name": "نام و نام خانوادگی مادر",
    "guardian.mother.national_id": "کد ملی مادر",
    "guardian.mother.birth_date": "تاریخ تولد مادر",
    "guardian.mother.mobile": "موبایل مادر",
    "guardian.mother.education_level": "تحصیلات مادر",
    "guardian.mother.field_of_study": "رشته تحصیلی مادر",
    "guardian.mother.employment_status": "وضعیت اشتغال مادر",
    "guardian.mother.occupation": "شغل مادر",
    "guardian.mother.workplace_address": "آدرس محل کار مادر",
    # Other guardian
    "guardian.other.full_name": "نام سرپرست دیگر",
    "guardian.other.national_id": "کد ملی سرپرست دیگر",
    "guardian.other.mobile": "موبایل سرپرست دیگر",
    "guardian.other.relation": "نسبت سرپرست دیگر",
    # Admission / previous
    "admission.quota": "سهمیه",
    "admission.previous_school_name": "مدرسه قبلی",
    "admission.previous_average": "معدل قبلی",
    "admission.previous_discipline_score": "نمره انضباط قبلی",
}

# Groups of fields, used to render the mapping UI in sections.
CANONICAL_FIELD_GROUPS = [
    ("identity", "هویت دانش‌آموز", [
        "student.first_name", "student.last_name", "student.full_name",
        "student.national_id", "student.source_student_code",
        "student.birth_date", "student.gender", "student.birth_place",
    ]),
    ("enrollment", "ثبت‌نام", [
        "enrollment.grade", "enrollment.classroom_title",
        "enrollment.admission_status",
    ]),
    ("contacts", "تماس", [
        "contacts.student_mobile", "contacts.emergency_mobile",
        "contacts.emergency_contact_relation", "contacts.home_phone",
        "contacts.home_address", "contacts.postal_code",
        "contacts.student_lives_with",
    ]),
    ("guardian_father", "اطلاعات پدر", [
        k for k in CANONICAL_FIELDS if k.startswith("guardian.father.")
    ]),
    ("guardian_mother", "اطلاعات مادر", [
        k for k in CANONICAL_FIELDS if k.startswith("guardian.mother.")
    ]),
    ("guardian_other", "سرپرست دیگر", [
        k for k in CANONICAL_FIELDS if k.startswith("guardian.other.")
    ]),
    ("admission", "سوابق و سهمیه", [
        "admission.quota", "admission.previous_school_name",
        "admission.previous_average", "admission.previous_discipline_score",
    ]),
]


# Common grade labels in Iranian schools.
GRADES = {
    "پیش‌دبستانی", "آمادگی",
    "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم",
    "هفتم", "هشتم", "نهم",
    "دهم", "یازدهم", "دوازدهم",
}

# Map common variants to normalized grade labels.
GRADE_ALIASES = {
    "پایه اول": "اول", "پایه 1": "اول", "1": "اول",
    "پایه دوم": "دوم", "پایه 2": "دوم", "2": "دوم",
    "پایه سوم": "سوم", "پایه 3": "سوم", "3": "سوم",
    "پایه چهارم": "چهارم", "پایه 4": "چهارم", "4": "چهارم",
    "پایه پنجم": "پنجم", "پایه 5": "پنجم", "5": "پنجم",
    "پایه ششم": "ششم", "پایه 6": "ششم", "6": "ششم",
    "پایه هفتم": "هفتم", "پایه 7": "هفتم", "7": "هفتم",
    "پایه هشتم": "هشتم", "پایه 8": "هشتم", "8": "هشتم",
    "پایه نهم": "نهم", "پایه 9": "نهم", "9": "نهم",
    "پایه دهم": "دهم", "پایه 10": "دهم", "10": "دهم",
    "پایه یازدهم": "یازدهم", "پایه 11": "یازدهم", "11": "یازدهم",
    "پایه دوازدهم": "دوازدهم", "پایه 12": "دوازدهم", "12": "دوازدهم",
}


# Common labels that should be auto-suggested to a canonical field. The
# match is case/whitespace insensitive and after Persian character
# normalization (handed by the normalizer in phase 3). This is a seed
# list; more aliases are added as real school files arrive.
HEADER_SUGGESTIONS = {
    "student.first_name": ["نام", "اسم", "نام دانش آموز", "first name"],
    "student.last_name": [
        "نام خانوادگی", "فامیلی", "نام خانوادگي",
        "نام خانوادگی دانش آموز", "last name",
    ],
    "student.full_name": ["نام و نام خانوادگی", "نام کامل", "نام ونام خانوادگی"],
    "student.national_id": [
        "کدملی", "کد ملی", "کدملي", "کد ملي", "national id", "nationalid",
        "شماره ملی", "شماره شناسنامه",
    ],
    "student.source_student_code": [
        "کد دانش آموزی", "کد دانش آموز", "کد پرونده", "شماره پرونده",
        "شماره داوطلبی", "کد ثبت نام", "شناسه دانش آموز", "student code",
    ],
    "student.birth_date": [
        "تاریخ تولد", "تاريخ تولد", "تولد", "birth date",
    ],
    "student.gender": ["جنسیت", "جنسيت", "gender", "sex"],
    "student.birth_place": ["محل تولد", "محل تولد دانش آموز"],

    "enrollment.grade": ["پایه", "پايه", "مقطع", "grade"],
    "enrollment.classroom_title": [
        "کلاس", "شعبه", "گروه", "کلاس/شعبه", "class", "section",
    ],
    "enrollment.admission_status": ["وضعیت ثبت نام", "وضعیت", "admission status"],

    "contacts.student_mobile": [
        "موبایل دانش آموز", "همراه دانش آموز", "شماره همراه دانش آموز",
    ],
    "contacts.emergency_mobile": [
        "شماره همراه ضروری", "تلفن ضروری", "شماره تماس ضروری",
        "موبایل ضروری", "شماره اضطراری",
    ],
    "contacts.emergency_contact_relation": ["نسبت تماس ضروری", "نسبت"],
    "contacts.home_phone": ["تلفن ثابت", "تلفن منزل", "منزل"],
    "contacts.home_address": ["آدرس", "ادرس", "آدرس منزل", "آدرس دقیق محل سکونت"],
    "contacts.postal_code": ["کد پستی", "کدپستی"],
    "contacts.student_lives_with": ["زندگی با", "وضعیت زندگی"],

    "guardian.father.first_name": ["نام پدر"],
    "guardian.father.last_name": ["نام خانوادگی پدر"],
    "guardian.father.full_name": ["نام و نام خانوادگی پدر", "نام پدر"],
    "guardian.father.national_id": ["کد ملی پدر", "کدملی پدر"],
    "guardian.father.mobile": ["موبایل پدر", "شماره همراه پدر", "تلفن پدر"],
    "guardian.father.occupation": ["شغل پدر"],
    "guardian.father.education_level": ["تحصیلات پدر"],
    "guardian.father.field_of_study": ["رشته تحصیلی پدر"],

    "guardian.mother.first_name": ["نام مادر"],
    "guardian.mother.last_name": ["نام خانوادگی مادر"],
    "guardian.mother.full_name": ["نام و نام خانوادگی مادر"],
    "guardian.mother.national_id": ["کد ملی مادر", "کدملی مادر"],
    "guardian.mother.mobile": ["موبایل مادر", "شماره همراه مادر", "تلفن مادر"],
    "guardian.mother.occupation": ["شغل مادر"],
    "guardian.mother.education_level": ["تحصیلات مادر"],
    "guardian.mother.field_of_study": ["رشته تحصیلی مادر"],

    "guardian.other.full_name": ["نام قیم", "نام ولی"],
    "guardian.other.relation": ["نسبت ولی", "نوع رابطه"],

    "admission.quota": ["سهمیه", "سهميه"],
    "admission.previous_school_name": ["مدرسه قبلی", "مدرسه مبدا"],
    "admission.previous_average": ["معدل قبلی", "معدل"],
    "admission.previous_discipline_score": ["انضباط", "نمره انضباط"],
}
