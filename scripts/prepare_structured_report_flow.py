"""Prepare standard-connector HTML reporting; no native calls or activation."""
import copy
import hashlib
import json
from urllib.parse import urlsplit

def compose(value, previous=""):
    return {"type": "Compose", "inputs": value,
            "runAfter": {previous: ["Succeeded"]} if previous else {}}


def gate(expression, previous):
    # Preserve the accepted fail-closed expression, including inside loops.
    return compose("@if(" + expression + ",true,json('QGIP_SOURCE_GUARD_FAILED'))", previous)


def base(site, archive_parent, reference):
    parsed = urlsplit(site)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".sharepoint.com")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or site.endswith("/") or any(ord(c) < 32 for c in site)):
        raise ValueError("Qualified existing SharePoint site URL required")
    if (not archive_parent.startswith("/Documents/") or archive_parent.endswith("/")
            or any(c in archive_parent for c in "'?#%\\")
            or ".." in archive_parent.split("/")
            or any(ord(c) < 32 for c in archive_parent)):
        raise ValueError("Qualified existing Documents archive parent required")
    if (reference.get("source") != "Embedded"
            or reference.get("id") != "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
            or not reference.get("connectionReferenceLogicalName")
            or not isinstance(reference.get("connectionName"), str)
            or not reference["connectionName"].strip()):
        raise ValueError("Qualified existing Embedded SharePoint reference required")
    # Portal expansion schemas are diagnostic metadata, not connection identity.
    ref = {k: copy.deepcopy(v) for k, v in reference.items()
           if k not in ("apiDefinition", "operationDefinitions")}

    return {"properties": {"displayName": NAME, "state": "Stopped",
        "connectionReferences": {"shared_sharepointonline": ref}, "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "contentVersion": "1.0.0.0", "parameters": {
                "$authentication": {"type": "SecureObject", "defaultValue": {}},
                "$connections": {"type": "Object", "defaultValue": {}}},
            "triggers": {"manual": {"type": "Request", "kind": "Button", "inputs": {"schema": {}},
                "runtimeConfiguration": {"concurrency": {"runs": 1}}}}, "actions": {}}}}


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def escaped(expression):
    value = f"string(coalesce({expression},''))"
    for old, new in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'),
                     ('"', '&quot;'), ("'", '&#39;')):
        value = f'replace({value},{literal(old)},{literal(new)})'
    return value

NAME = 'CHHHS RIMS | Publications | Structured monthly report'
TEMPLATE = '''<!doctype html><html lang="en-AU"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Monthly publications report</title><style>body{font:16px/1.5 Georgia,serif;max-width:960px;margin:2rem auto;padding:1rem}h1{color:#005c8a}h2{font-size:1.2rem}article{border-top:1px solid #aaa;padding:1rem 0}pre,dd{white-space:pre-wrap;overflow-wrap:anywhere}dt{font-weight:bold}dd{margin:0 0 .5rem}a{overflow-wrap:anywhere}@media print{@page{size:A4;margin:18mm}body{margin:0;font-size:10pt}h2{break-after:avoid}}</style><body><h1>Monthly research publications report</h1><p>System-generated draft. Substantive review and authority to issue remain pending.</p>'''
VERSION = hashlib.sha256(TEMPLATE.encode()).hexdigest()
HOSTS = ['https://pubmed.ncbi.nlm.nih.gov/', 'https://dora.health.qld.gov.au/',
         'https://doi.org/', 'https://europepmc.org/', 'https://pmc.ncbi.nlm.nih.gov/']


def build(site, reporting_parent, reference, default_input_path):
    if (not default_input_path.startswith(reporting_parent + '/')
            or not default_input_path.endswith('.json')
            or any(c in default_input_path for c in "'?#%\\")
            or '..' in default_input_path.split('/')):
        raise ValueError('Exact reporting input path required')
    d = base(site, reporting_parent, reference)
    p = d['properties']; p['displayName'] = NAME
    df = p['definition']; df['triggers']['manual']['inputs']['schema'] = {
        'type': 'object', 'properties': {'report_input_path': {'type': 'string',
            'title': 'Prepared report JSON path (optional)', 'description':
            'Use an immutable reconciled input in the existing reporting folder.'}}}
    df['triggers']['manual']['runtimeConfiguration'] = {'concurrency': {'runs': 1}}
    a = df['actions'] = {}

    def sp(op, params, previous):
        return {'type': 'OpenApiConnection', 'runAfter': {previous: ['Succeeded']},
            'inputs': {'host': {'apiId': '/providers/Microsoft.PowerApps/apis/shared_sharepointonline',
                'connectionName': 'shared_sharepointonline', 'operationId': op},
                'parameters': {'dataset': site, **params}, 'retryPolicy': {'type': 'none'}}}

    def read(path, previous):
        return sp('GetFileContentByPath', {'path': path, 'inferContentType': False}, previous)

    def save_verify(actions, key, name, content, previous):
        actions['Save_' + key] = sp('CreateFile', {'folderPath': "@outputs('Output_folder')",
            'name': name, 'body': '@base64ToBinary(base64(' + content + '))'}, previous)
        actions['Read_' + key] = read("@concat(outputs('Output_folder'),'/'" +
            ',' + literal(name) + ')', 'Save_' + key)
        actions['Verify_' + key] = gate('equals(base64(' + content + "),body('Read_" + key + "')?['$content'])", 'Read_' + key)
        return 'Verify_' + key

    a['Input_path'] = compose("@coalesce(triggerBody()?['report_input_path']," + literal(default_input_path) + ')')
    a['Guard_path'] = gate("and(startsWith(outputs('Input_path')," + literal(reporting_parent + '/') +
        "),endsWith(outputs('Input_path'),'.json'),not(contains(outputs('Input_path'),'..')))", 'Input_path')
    a['Read_input'] = read("@outputs('Input_path')", 'Guard_path')
    a['Input'] = compose("@json(base64ToString(body('Read_input')?['$content']))", 'Read_input')
    a['Select_keys'] = {'type': 'Select', 'runAfter': {'Input': ['Succeeded']},
        'inputs': {'from': "@outputs('Input')?['records']", 'select': "@item()?['CanonicalKey']"}}
    a['Select_bibliography_keys'] = {'type': 'Select', 'runAfter': {'Select_keys': ['Succeeded']},
        'inputs': {'from': "@outputs('Input')?['fields']?['Bibliography']", 'select': "@item()?['CanonicalKey']"}}
    a['Guard_complete'] = gate("and(equals(outputs('Input')?['format'],'rims-structured-monthly-report-input-v1')," +
        "equals(outputs('Input')?['status'],'prepared-not-generated')," +
        "equals(body('Select_keys'),json(outputs('Input')?['fields']?['IncludedCanonicalKeys']))," +
        "equals(body('Select_keys'),body('Select_bibliography_keys'))," +
        "equals(length(body('Select_keys')),length(union(body('Select_keys'),body('Select_keys'))))," +
        "equals(length(body('Select_keys')),int(outputs('Input')?['fields']?['IncludedRecordCount']))," +
        "equals(length(body('Select_keys')),outputs('Input')?['reconciliation']?['monthly_count'])," +
        "equals(outputs('Input')?['fields']?['ReportingMonth'],outputs('Input')?['reconciliation']?['reporting_month'])," +
        "equals(length(outputs('Input')?['fields']?['Bibliography']),length(body('Select_keys'))))", 'Select_bibliography_keys')
    a['Revision'] = compose("@outputs('Input')?['fields']?['OutputRevision']", 'Guard_complete')
    a['Guard_revision'] = gate("and(not(empty(outputs('Revision'))),lessOrEquals(length(outputs('Revision')),80)," +
        ','.join("not(contains(outputs('Revision')," + literal(x) + '))' for x in
                 ['/', '\\', '..', "'", '#', '%', '?', ':']) +
        ",not(contains(outputs('Revision'),decodeUriComponent('%0A'))),not(contains(outputs('Revision'),decodeUriComponent('%0D'))))", 'Revision')
    a['Period'] = compose("@outputs('Input')?['fields']?['ReportingMonth']", 'Guard_revision')
    a['Guard_period'] = gate("and(equals(length(outputs('Period')),7),equals(substring(outputs('Period'),4,1),'-')," +
        "greaterOrEquals(int(substring(outputs('Period'),0,4)),1900)," +
        "greaterOrEquals(int(substring(outputs('Period'),5,2)),1),lessOrEquals(int(substring(outputs('Period'),5,2)),12))", 'Period')
    a['Output_folder'] = compose("@concat(" + literal(reporting_parent + '/structured-report-') +
        ",outputs('Period'),'-',outputs('Revision'))", 'Guard_period')
    a['Initialize_articles'] = {'type': 'InitializeVariable', 'runAfter': {'Output_folder': ['Succeeded']},
        'inputs': {'variables': [{'name': 'Articles', 'type': 'array', 'value': []}]}}
    a['Initialize_links'] = {'type': 'InitializeVariable', 'runAfter': {'Initialize_articles': ['Succeeded']},
        'inputs': {'variables': [{'name': 'Links', 'type': 'array', 'value': []}]}}
    body = {'Reset_links': {'type': 'SetVariable', 'inputs': {'name': 'Links', 'value': []}, 'runAfter': {}}}
    link = "items('For_each_link')"
    body['For_each_link'] = {'type': 'Foreach', 'foreach': "@split(items('For_each_citation')?['SourceURL'],decodeUriComponent('%0A'))",
        'runAfter': {'Reset_links': ['Succeeded']}, 'runtimeConfiguration': {'concurrency': {'repetitions': 1}},
        'actions': {'Keep_safe_link': {'type': 'If', 'expression': '@or(' +
            ','.join('startsWith(' + link + ',' + literal(h) + ')' for h in HOSTS) + ')',
            'runAfter': {}, 'actions': {'Append_link': {'type': 'AppendToArrayVariable', 'runAfter': {},
                'inputs': {'name': 'Links', 'value': '@concat(\'<a href="\',' + escaped(link) +
                    ',\'" rel="noreferrer">\',' + escaped(link) + ",'</a>')"}}}, 'else': {'actions': {}}}}}
    body['Append_article'] = {'type': 'AppendToArrayVariable', 'runAfter': {'For_each_link': ['Succeeded']},
        'inputs': {'name': 'Articles', 'value': "@concat('<article data-key=\"'," +
            escaped("items('For_each_citation')?['CanonicalKey']") + ",'\"><h2>'," +
            escaped("items('For_each_citation')?['CanonicalKey']") + ",'</h2><pre>'," +
            escaped("items('For_each_citation')?['Citation']") + ",'</pre><p>',join(variables('Links'),'<br>')," +
            "'</p><p>Affiliation evidence: '," + escaped("items('For_each_citation')?['AffiliationEvidence']") +
            ",'</p><p>Source date and precision: '," + escaped("items('For_each_citation')?['DateUncertainty']") + ",'</p></article>')"}}
    a['For_each_citation'] = {'type': 'Foreach', 'foreach': "@outputs('Input')?['fields']?['Bibliography']",
        'runAfter': {'Initialize_links': ['Succeeded']}, 'runtimeConfiguration': {'concurrency': {'repetitions': 1}}, 'actions': body}
    pieces = [literal(TEMPLATE)]
    for field, title in [('ReportingMonth', 'Reporting month'), ('ExecutiveSummary', 'Summary'),
        ('AttributionAndFundingContext', 'Attribution and funding context'),
        ('SourceAndDateUncertainty', 'Coverage and uncertainty')]:
        pieces += [literal('<h2>' + title + '</h2><pre>'), escaped("outputs('Input')?['fields']?['" + field + "']"), literal('</pre>')]
    pieces += [literal('<h2>Complete bibliography</h2>'), "join(variables('Articles'),'')",
        literal('<h2>Generation record</h2><pre>'), escaped("string(outputs('Input')?['reconciliation'])"),
        literal('</pre><p>Output revision: '), escaped("outputs('Revision')"),
        literal('</p><p>Input preparation time: '), escaped("outputs('Input')?['fields']?['GeneratedAt']"), literal('</p></body></html>')]
    a['HTML'] = compose('@concat(' + ','.join(pieces) + ')', 'For_each_citation')
    a['Read_existing_manifest'] = read("@concat(outputs('Output_folder'),'/manifest.json')", 'HTML')
    existing = {'Parse_existing': compose("@json(base64ToString(body('Read_existing_manifest')?['$content']))")}
    existing['Read_previous_source'] = read("@concat(outputs('Output_folder'),'/source-input.json')", 'Parse_existing')
    existing['Read_previous_report'] = read("@concat(outputs('Output_folder'),'/report.html')", 'Read_previous_source')
    existing['Guard_unchanged'] = gate("and(equals(outputs('Parse_existing')?['complete'],true)," +
        "equals(outputs('Parse_existing')?['html_template_sha256']," + literal(VERSION) + '),' +
        "equals(body('Read_previous_source')?['$content'],body('Read_input')?['$content'])," +
        "equals(body('Read_previous_report')?['$content'],base64(outputs('HTML'))))", 'Read_previous_report')
    existing['Replay_result'] = compose({'status': 'UNCHANGED_NO_WRITE', 'folder': "@outputs('Output_folder')"}, 'Guard_unchanged')
    new = {'Require_missing': gate("equals(outputs('Read_existing_manifest')?['statusCode'],404)", '')}
    new['Create_folder'] = sp('HttpRequest', {'parameters/method': 'POST', 'parameters/uri': '_api/web/folders',
        'parameters/headers': {'Accept': 'application/json;odata=nometadata', 'Content-Type': 'application/json;odata=nometadata'},
        'parameters/body': {'ServerRelativeUrl': '@concat(' + literal(urlsplit(site).path) + ",outputs('Output_folder'))"}}, 'Require_missing')
    new['Require_exclusive_folder'] = gate("and(equals(outputs('Create_folder')?['statusCode'],201),equals(int(body('Create_folder')?['ItemCount']),0))", 'Create_folder')
    last = save_verify(new, 'source', 'source-input.json', "base64ToString(body('Read_input')?['$content'])", 'Require_exclusive_folder')
    last = save_verify(new, 'report', 'report.html', "outputs('HTML')", last)
    new['Manifest'] = compose({'format': 'rims-structured-html-report-v1', 'complete': True,
        'html_template_sha256': VERSION, 'source_input_path': "@outputs('Input_path')",
        'reporting_month': "@outputs('Period')", 'output_revision': "@outputs('Revision')",
        'included_keys': "@body('Select_keys')", 'included_count': "@length(body('Select_keys'))",
        'source_context': "@outputs('Input')?['reconciliation']", 'generated_at_utc': '@utcNow()',
        'run': "@workflow()?['run']?['name']", 'files': ['source-input.json', 'report.html']}, last)
    last = save_verify(new, 'manifest', 'manifest.json', "string(outputs('Manifest'))", 'Manifest')
    new['Generation_result'] = compose({'status': 'GENERATED_VERIFIED', 'folder': "@outputs('Output_folder')"}, last)
    a['Existing_or_new'] = {'type': 'If', 'expression': "@equals(outputs('Read_existing_manifest')?['statusCode'],200)",
        'runAfter': {'Read_existing_manifest': ['Succeeded', 'Failed', 'TimedOut']},
        'actions': existing, 'else': {'actions': new}}
    return d
