export type Role = "system_admin" | "school_operator";

export interface School {
  id: number;
  name: string;
  external_code: string;
}

export interface Me {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
  role_display: string;
  school: School | null;
  is_active: boolean;
  last_login: string | null;
  must_change_password: boolean;
}
