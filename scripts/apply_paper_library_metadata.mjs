/** Operator-run conditional Title/Description update; no content/manifest writes. */
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import {execFileSync} from 'node:child_process';
async function main(){
const [targetPath,planPath,output,cliRoot]=process.argv.slice(2);
if(!targetPath||!planPath||!output)throw Error('Usage: node apply_paper_library_metadata.mjs target.json plan.json private/ops/new-output [M365-CLI-dist]');
const target=JSON.parse(fs.readFileSync(targetPath)),plan=JSON.parse(fs.readFileSync(planPath));
const out=path.resolve(output),privateRoot=path.resolve('private/ops')+path.sep;
if(!out.startsWith(privateRoot)||fs.existsSync(out))throw Error('New private/ops output directory required');
const site=new URL(target.site_url);if(site.protocol!=='https:'||!site.hostname.endsWith('.sharepoint.com')||site.username||site.password||site.search||site.hash)throw Error('Qualified SharePoint site required');
const guid=/^[a-f0-9-]{36}$/i;for(const id of [target.library_id,target.list_id,plan.file_id])if(!guid.test(id))throw Error('Invalid exact target identity');
if(!Number.isInteger(plan.parent_id)||!Number.isInteger(plan.item_id)||plan.content_writes!==false||plan.manifest_writes!==false)throw Error('Invalid metadata-only plan');
const itemUrl=target.site_url+"/_api/web/lists(guid'"+target.library_id+"')/items("+plan.item_id+")";
if(plan.item_url!==itemUrl||Object.keys(plan.changes).some(k=>!['Title','OData__ExtendedDescription'].includes(k)))throw Error('Plan outside exact two-field item scope');
fs.mkdirSync(out);const save=(name,value)=>fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(value,null,2)+'\n',{mode:0o600,flag:'wx'});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const canonical=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
const normal=s=>String(s??'').replace(/&#x([a-f0-9]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16))).replace(/&#([0-9]+);/g,(_,n)=>String.fromCodePoint(Number(n))).replace(/&(amp|lt|gt|quot|apos);/g,(_,n)=>({amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"}[n])).replace(/href="([^"]*)"/g,(whole,href)=>{const u=new URL(href,site.origin+'/');return u.origin===site.origin?'href="'+u.href+'"':whole;}).replace(/<[^>]+>/g,s=>s.replace(/\s+/g,' '));
const dist=cliRoot||path.join(execFileSync('npm',['root','-g'],{encoding:'utf8'}).trim(),'@pnp/cli-microsoft365/dist');
const {default:auth}=await import(path.join(dist,'Auth.js'));await auth.restoreAuth();auth.ensureAccessTokenWithBrowser=async()=>{throw Error('Use qualified workload authentication recovery before retry');};auth.ensureAccessTokenWithDeviceCode=async()=>{throw Error('Use qualified workload authentication recovery before retry');};
const {executeCommand}=await import(path.join(dist,'api.js'));await executeCommand('request',{url:target.site_url+'/_api/web?$select=Id',method:'get',output:'none'});const request=(await import(path.join(dist,'request.js'))).default;request.logger={log:async()=>{},logToStderr:async()=>{}};
let submitted=false;request.req.interceptors.request.use(config=>{config.maxRedirects=0;const method=(config.method||'get').toUpperCase();if(!['GET','HEAD','OPTIONS'].includes(method)){if(method!=='POST'||config.url!==itemUrl||submitted)throw Error('Out-of-scope/repeated metadata effect refused; reconcile saved item');submitted=true;fs.appendFileSync(path.join(out,'transport.jsonl'),JSON.stringify({method,url:config.url,fields:Object.keys(plan.changes),submitted_utc:new Date().toISOString()})+'\n');}return config;});
const get=async url=>request.get({url,headers:{accept:'application/json;odata=minimalmetadata'},responseType:'json'});
const parentUrl=target.site_url+"/_api/web/lists(guid'"+target.list_id+"')/items("+plan.parent_id+")?$select=Id,Title,field_2,field_11,OAArchiveState,OAArchiveURL,OAArchiveManifest";
const parentGet=async()=>request.get({url:parentUrl,headers:{accept:'application/json;odata=nometadata'},responseType:'json'});
const base=target.site_url+"/_api/web/GetFileById('"+plan.file_id+"')";
const fileGet=()=>get(base+'?$select=UniqueId,Name,ServerRelativeUrl,Length,ETag,CheckOutType,MajorVersion,MinorVersion,UIVersionLabel,TimeLastModified');
const itemGet=()=>get(itemUrl+'?$select=*,OData__ExtendedDescription');
const bytesGet=async suffix=>Buffer.from(await request.get({url:base+(suffix||'/$value'),headers:{accept:'application/octet-stream'},responseType:'arraybuffer'}));
const before=await itemGet(),file=await fileGet(),parent=await parentGet();save('item-before',before);save('file-before',file);save('parent-before',parent);
const pointer=await get(base+'/ListItemAllFields?$select=Id');if(pointer.Id!==plan.item_id||before.Id!==plan.item_id)throw Error('Exact file/item association changed');const manifest=JSON.parse(parent.OAArchiveManifest);if(parent.OAArchiveState!=='linked'||manifest.state!=='linked'||manifest.verified_file_unique_id!==plan.file_id||manifest.sha256!==plan.sha256||manifest.file_url!==plan.file_url||parent.OAArchiveURL?.Url!==plan.file_url||manifest.CanonicalKey!==parent.field_2||manifest.DOI!==parent.field_11||file.ServerRelativeUrl!==manifest.folder+'/paper.pdf'||!manifest.folder.startsWith(target.folder+'/paper-'+plan.parent_id+'-')||file.CheckOutType!==2||file.Name!=='paper.pdf')throw Error('Current linked archive identity drift; no write');
// Compare the authoritative parent fields directly with the pinned snapshot.
const pinnedBytes=fs.readFileSync(plan.snapshot_path);if(sha(pinnedBytes)!==plan.snapshot_sha256)throw Error('Pinned snapshot changed after preparation');const pinned=JSON.parse(pinnedBytes);if(canonical(parent)!==canonical(pinned.parent))throw Error('Authoritative parent changed; no write');
const fields=await get(target.site_url+"/_api/web/lists(guid'"+target.library_id+"')/fields?$select=InternalName,TypeAsString,ReadOnlyField,RichText&$top=500");
for(const [name,type] of [['Title','Text'],['_ExtendedDescription','Note']]){const f=fields.value.find(f=>f.InternalName===name);if(!f||f.TypeAsString!==type||f.ReadOnlyField||(type==='Note'&&!f.RichText))throw Error('Exact existing field contract changed');}
const access=await get(base+'/ListItemAllFields?$select=Id,HasUniqueRoleAssignments'),versions=await get(base+'/Versions?$select=ID,VersionLabel,Created,IsCurrentVersion');save('access-before',access);save('versions-before',versions);const bytes=await bytesGet();if(sha(bytes)!==plan.sha256||bytes.length!==Number(file.Length)||!bytes.subarray(0,5).equals(Buffer.from('%PDF-')))throw Error('PDF integrity drift; no write');
const already=Object.entries(plan.changes).every(([k,v])=>k==='OData__ExtendedDescription'?normal(before[k])===normal(v):before[k]===v);
if(already){save('acceptance',{status:'PASS_NO_CHANGE',writes:0,sha256:plan.sha256,file_identity:plan.file_id,content_unchanged:true,manifest_unchanged:true});console.log('PASS_NO_CHANGE; zero writes');process.exit(0);}
if((before['odata.etag']||before['@odata.etag'])!==plan.etag||plan.etag==='*'||file.ETag!==plan.file_preimage.ETag||JSON.stringify(file.UniqueId)!==JSON.stringify(plan.file_id))throw Error('Exact item/file ETag changed; no write');
for(const [k,v] of Object.entries(plan.before))if((before[k]??null)!==(v??null))throw Error('Metadata preimage changed; preserve human edits');

const immediate=await itemGet(),immediateFile=await fileGet();if((immediate['odata.etag']||immediate['@odata.etag'])!==plan.etag||immediateFile.ETag!==file.ETag)throw Error('Item/file changed after preflight');
await request.post({url:itemUrl,headers:{accept:'application/json;odata=nometadata','content-type':'application/json;odata=nometadata','IF-MATCH':plan.etag,'X-HTTP-Method':'MERGE'},data:plan.changes,responseType:'json'});
const after=await itemGet(),savedFile=await fileGet(),savedParent=await parentGet();save('item-after',after);save('file-after',savedFile);save('parent-after',savedParent);
for(const [k,v] of Object.entries(plan.changes))if(k==='OData__ExtendedDescription'?normal(after[k])!==normal(v):after[k]!==v)throw Error('Saved metadata differs; reconcile before retry');
if(canonical(savedParent)!==canonical(parent))throw Error('Authoritative parent/link/manifest changed');
const ignored=new Set(['Title','OData__ExtendedDescription','Modified','EditorId','EditorStringId','OData__UIVersionString','odata.etag','@odata.etag','odata.id']);for(const k of new Set([...Object.keys(before),...Object.keys(after)]))if(!ignored.has(k)&&JSON.stringify(before[k])!==JSON.stringify(after[k]))throw Error('Unrelated item field changed: '+k);
const savedBytes=await bytesGet();if(sha(savedBytes)!==plan.sha256||savedFile.UniqueId!==file.UniqueId||savedFile.ServerRelativeUrl!==file.ServerRelativeUrl||savedFile.Length!==file.Length)throw Error('File content/identity/path changed');
const afterAccess=await get(base+'/ListItemAllFields?$select=Id,HasUniqueRoleAssignments');if(afterAccess.HasUniqueRoleAssignments!==access.HasUniqueRoleAssignments)throw Error('Access shape changed');
const afterVersions=await get(base+'/Versions?$select=ID,VersionLabel,Created,IsCurrentVersion');save('versions-after',afterVersions);if(afterVersions['odata.nextLink']||afterVersions['@odata.nextLink'])throw Error('History pagination needs reconciliation');for(const old of versions.value)if(!afterVersions.value.some(v=>v.ID===old.ID&&v.VersionLabel===old.VersionLabel&&v.Created===old.Created))throw Error('Prior history changed');
const priorLabel=file.UIVersionLabel||file.MajorVersion+'.'+file.MinorVersion;const prior=afterVersions.value.find(v=>v.VersionLabel===priorLabel);if(!prior)throw Error('Pre-update version missing');const priorBytes=await bytesGet('/Versions('+prior.ID+')/$value');if(sha(priorBytes)!==plan.sha256)throw Error('Prior-version PDF differs');
save('acceptance',{status:'PASS_PAPER_LIBRARY_METADATA_PRESERVATION',writes:1,fields:Object.keys(plan.changes),sha256:plan.sha256,file_identity:plan.file_id,source_version:priorLabel,current_version:savedFile.UIVersionLabel||savedFile.MajorVersion+'.'+savedFile.MinorVersion,prior_version_retrieved:true,prior_versions_preserved:true,content_unchanged:true,link_and_manifest_unchanged:true,unrelated_item_fields_preserved:true,access_shape_unchanged:true,metadata_changes_advance_file_etag:true});console.log('PASS_PAPER_LIBRARY_METADATA_PRESERVATION; one guarded metadata update');

}
main().catch(error=>{console.error(error instanceof Error?error.message:'Metadata operation failed; reconcile the private receipt before retry');process.exitCode=1;});
