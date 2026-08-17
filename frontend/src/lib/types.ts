export interface Me { id:number; username:string; email:string; is_active:boolean; roles:string[]; perms:string[]; project_perms?:Record<string,string[]> }
export interface ListResponse<T> { items:T[]; total:number; limit:number; offset:number }
export interface UserItem { id:number; username:string; email:string; is_active:boolean; created_at?:string; roles:string[] }
export type ProjectRole = "owner" | "maintainer" | "developer" | "operator" | "viewer";
export interface ProjectMember { user_id:number; username:string; role:ProjectRole }
export type CredentialKind = "ssh_key" | "ssh_password" | "vault_password" | "become_password";
export interface Credential { id:number; project_id:number; name:string; kind:CredentialKind; username?:string|null; created_by:number }
export interface Project { id:number; name:string; git_path:string; default_branch:string; is_inventory_repo:boolean }
export interface Playbook { id:number; project_id:number; rel_path:string; name:string }
export interface PlaybookFile { id:number; rel_path:string; content:string; sha:string }
export type InventoryFormat = "yaml" | "ini";
export interface Inventory { id:number; rel_path:string; name:string; format:InventoryFormat }
export interface InventoryFile { id:number; rel_path:string; format:InventoryFormat; content:string; sha:string }
export type SurveyFieldType = "text" | "textarea" | "password" | "integer" | "boolean" | "choice";
export interface SurveyField { var:string; label:string; type:SurveyFieldType; required:boolean; default:string|number|boolean|null; choices:string[]; min:number|null; max:number|null }
export interface JobTemplate { id:number; project_id:number; name:string; description?:string|null; playbook_id:number; inventory_id:number; limit_pattern?:string|null; tags?:string|null; skip_tags?:string|null; extra_vars:Record<string,unknown>; verbosity:number; forks:number; credential_ids:number[]; requires_approval:boolean; diff_mode:boolean; survey_spec:SurveyField[]; ask_limit:boolean; ask_tags:boolean; ask_skip_tags:boolean; ask_extra_vars:boolean; ask_verbosity:boolean; ask_diff:boolean; ask_credentials:boolean; ask_inventory:boolean; ask_mode:boolean }
export type JobStatus = "pending_approval" | "approved" | "rejected" | "queued" | "running" | "successful" | "failed" | "canceled" | "timed_out";
export type JobMode = "check" | "live";
export const TERMINAL_JOB_STATUSES: JobStatus[] = ["successful", "failed", "canceled", "timed_out", "rejected"];
export interface JobListItem { id:number; template_id?:number|null; playbook_id:number; inventory_id:number; mode:JobMode; status:JobStatus; requested_by:number; approved_by?:number|null; created_at?:string|null; finished_at?:string|null }
export interface OverrideValue { template:unknown; request:unknown }
export interface JobDetail extends JobListItem { approval_note?:string|null; rc?:number|null; stats?:Record<string,unknown>|null; params_snapshot?:Record<string,unknown>|null; overrides?:Record<string,OverrideValue>; started_at?:string|null; relaunch_of_id?:number|null }
export interface JobReportTask { uuid?:string|null; name?:string|null; action?:string|null; duration_ms:number; results:Record<string,number>; failed_hosts:string[]; first_failure_counter?:number|null }
export interface JobReportPlay { uuid?:string|null; name?:string|null; duration_ms:number; tasks:JobReportTask[] }
export interface HostSummaryRow { host:string; ok:number; changed:number; failed:number; unreachable:number; skipped:number; status:"ok"|"changed"|"failed"|"unreachable"|"skipped"; first_failure_counter?:number|null }
export interface JobReport { plays:JobReportPlay[]; hosts:HostSummaryRow[]; totals:Record<string,number> }
export interface Schedule { id:number; template_id:number; name:string; cron_expr:string; timezone:string; enabled:boolean; created_by:number }
export interface Notification { id:number; name:string; kind:"webhook"|"slack"; url:string; enabled:boolean; on_success:boolean; on_failure:boolean; on_approval_needed:boolean; created_by:number }
export interface FileEntry { rel_path:string; name:string; type:"dir"|"file"; size:number }
export interface TreeResponse { entries:FileEntry[]; truncated:boolean }
export interface FileContent { rel_path:string; content:string; is_vault:boolean; sha:string }
export interface CommitInfo { sha:string; message:string; author_user_id?:number|null; files_changed:string[]; created_at?:string|null }
export interface AuditItem { id:number; actor_user_id?:number|null; action:string; object_type?:string|null; object_id?:string|null; detail?:Record<string,unknown>|null; ip?:string|null; created_at?:string|null }
export type PipelineStatus = "pending_approval" | "queued" | "running" | "successful" | "failed" | "canceled";
export interface PipelineStepInput { template_id:number; requires_approval:boolean; continue_on_failure:boolean }
export interface PipelineStep extends PipelineStepInput { position:number }
export interface Pipeline { id:number; project_id:number; name:string; description?:string|null; enabled:boolean; created_by:number; created_at?:string|null }
export interface PipelineDetail extends Pipeline { steps:{id:number; position:number; template_id:number; template_name:string; requires_approval:boolean; continue_on_failure:boolean}[] }
export interface PipelineRun { id:number; pipeline_id:number|null; status:PipelineStatus; requested_by:number; current_position:number; created_at?:string|null; started_at?:string|null; finished_at?:string|null }
export interface PipelineRunDetail extends PipelineRun { steps:{position:number; template_name:string; job_run_id?:number|null; status:JobStatus|"pending"}[] }
