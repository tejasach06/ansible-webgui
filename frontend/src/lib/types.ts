export interface Me { id:number; username:string; email:string; is_active:boolean; roles:string[]; perms:string[] }
export interface ListResponse<T> { items:T[]; total:number; limit:number; offset:number }
export interface UserItem { id:number; username:string; email:string; is_active:boolean; created_at?:string; roles:string[] }
export type CredentialKind = "ssh_key" | "ssh_password" | "vault_password" | "become_password";
export interface Credential { id:number; name:string; kind:CredentialKind; username?:string|null; created_by:number }
export interface Project { id:number; name:string; git_path:string; default_branch:string; is_inventory_repo:boolean }
export interface Playbook { id:number; project_id:number; rel_path:string; name:string }
export interface PlaybookFile { id:number; rel_path:string; content:string; sha:string }
export type InventoryFormat = "yaml" | "ini";
export interface Inventory { id:number; rel_path:string; name:string; format:InventoryFormat }
export interface InventoryFile { id:number; rel_path:string; format:InventoryFormat; content:string; sha:string }
export interface JobTemplate { id:number; project_id:number; name:string; playbook_id:number; inventory_id:number; limit_pattern?:string|null; tags?:string|null; skip_tags?:string|null; extra_vars:Record<string,unknown>; verbosity:number; forks:number; credential_ids:number[]; requires_approval:boolean }
export type JobStatus = "pending_approval" | "approved" | "rejected" | "queued" | "running" | "successful" | "failed" | "canceled" | "timed_out";
export type JobMode = "check" | "live";
export const TERMINAL_JOB_STATUSES: JobStatus[] = ["successful", "failed", "canceled", "timed_out", "rejected"];
export interface JobListItem { id:number; template_id?:number|null; playbook_id:number; inventory_id:number; mode:JobMode; status:JobStatus; requested_by:number; approved_by?:number|null; created_at?:string|null; finished_at?:string|null }
export interface JobDetail extends JobListItem { approval_note?:string|null; rc?:number|null; stats?:Record<string,unknown>|null; params_snapshot?:Record<string,unknown>|null; started_at?:string|null }
export interface Schedule { id:number; template_id:number; name:string; cron_expr:string; timezone:string; enabled:boolean; created_by:number }
export interface FileEntry { rel_path:string; name:string; type:"dir"|"file"; size:number }
export interface TreeResponse { entries:FileEntry[]; truncated:boolean }
export interface FileContent { rel_path:string; content:string; is_vault:boolean; sha:string }
export interface CommitInfo { sha:string; message:string; author_user_id?:number|null; files_changed:string[]; created_at?:string|null }
export interface AuditItem { id:number; actor_user_id?:number|null; action:string; object_type?:string|null; object_id?:string|null; detail?:Record<string,unknown>|null; ip?:string|null; created_at?:string|null }
