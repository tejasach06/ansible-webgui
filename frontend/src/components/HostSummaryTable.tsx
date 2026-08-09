import { DataTable } from "./DataTable";
import { StatusPill } from "./StatusPill";
import type { JobStatus } from "../lib/types";

export interface HostSummary { hosts:{host:string;ok:number;changed:number;failed:number;unreachable:number;skipped:number;status:string;first_failure_counter?:number|null}[]; totals:Record<string,number> }
export function HostSummaryTable({data}:{data?:HostSummary}){const rows=[...(data?.hosts??[])].sort((a,b)=>(a.status==="failed"||a.status==="unreachable"?-1:1)-(b.status==="failed"||b.status==="unreachable"?-1:1)||a.host.localeCompare(b.host)); return <DataTable rows={rows} empty="No host results yet" columns={[{key:"host",header:"Host",render:r=>r.host},{key:"ok",header:"ok",render:r=>r.ok},{key:"changed",header:"changed",render:r=>r.changed},{key:"failed",header:"failed",render:r=>r.failed},{key:"unreachable",header:"unreachable",render:r=>r.unreachable},{key:"skipped",header:"skipped",render:r=>r.skipped},{key:"status",header:"Status",render:r=><StatusPill status={(r.status==="unreachable"?"failed":r.status) as JobStatus}/>}]} />}
export default HostSummaryTable;
