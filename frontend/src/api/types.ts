export type Role =
  | "requester"
  | "lab_manager"
  | "institution_admin"
  | "auditor";

export type JudgeRole = "requester" | "manager" | "auditor";

export interface User {
  id: string;
  display_name: string;
  role: Role;
  organization_id: string;
  is_demo: boolean;
}

export interface DemoAccount {
  id: string;
  display_name: string;
  role: Role;
}

export interface PublicSummary {
  cities: {
    city: string;
    resource_count: number;
    organization_count: number;
  }[];
  categories: string[];
}

export interface APIErrorDetail {
  code: string;
  message: string;
}

export interface APIErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: APIErrorDetail[];
    request_id?: string;
  };
}
