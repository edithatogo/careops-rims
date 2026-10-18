"""Prepare a manual first-batch commit writer from the verified native export.

This is an operator-assisted bootstrap, not unattended batch acceptance. The
operator must independently correlate the supplied batch with its completed
refresh and successful extraction run. Native validation tables must be loaded
before this flow can pass. Packages and batch identifiers remain private.
"""
import argparse
import copy
import json
import uuid
import zipfile
from pathlib import Path

from build_native_retention_package import ROOT, after, compose


def build(baseline, output, batch):
    if not isinstance(batch, str):
        raise ValueError('batch must be a UUID string')
    try:
        batch = str(uuid.UUID(batch))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('batch must be a UUID string') from exc
    if not output.resolve().is_relative_to((ROOT / 'private').resolve()):
        raise ValueError('Package contains private connection references.')
    with zipfile.ZipFile(baseline) as z:
        files = {n: z.read(n) for n in z.namelist()}
    name = next(n for n in files if n.endswith('/definition.json'))
    document = json.loads(files[name])
    definition = document['properties']['definition']
    if list(definition['triggers']) != ['manual']:
        raise ValueError('Require a manual native baseline.')
    definition['triggers']['manual']['inputs']['schema'] = {
        'type': 'object', 'properties': {'text': {'title': 'Validated manifest',
        'type': 'string', 'x-ms-content-hint': 'TEXT', 'x-ms-dynamically-added': True}},
        'required': ['text']}
    old = definition['actions']
    query = copy.deepcopy(old['Run_a_query_against_a_dataset'])
    query['runAfter'] = {}
    query['inputs']['parameters']['specification/query'] = '''EVALUATE
ROW("Tests",COUNTROWS(RetentionValidation),
"Failed",COALESCE(COUNTROWS(FILTER(RetentionValidation,NOT(RetentionValidation[Passed] == TRUE()))),0),
"VerifiedSources",COUNTROWS(FILTER(StoredMetadataValidation,
StoredMetadataValidation[KeysMatch] == TRUE() && StoredMetadataValidation[MetadataValid] == TRUE() && StoredMetadataValidation[PayloadIdentitiesMatch] == TRUE() &&
((StoredMetadataValidation[Source] = "PubMed" && StoredMetadataValidation[ExpectedRecords] = 1261 && StoredMetadataValidation[ReconstructedRecords] = 1261 && StoredMetadataValidation[MetadataCharacters] = 32289819) ||
(StoredMetadataValidation[Source] = "DORA" && StoredMetadataValidation[ExpectedRecords] = 709 && StoredMetadataValidation[ReconstructedRecords] = 709 && StoredMetadataValidation[MetadataCharacters] = 2603915)))))'''
    actions = {'Read_native_validation': query,
               'Manifest': compose("@json(triggerBody()['text'])", 'Read_native_validation')}
    result = "body('Read_native_validation')['results'][0]['tables'][0]['rows'][0]"
    m = "outputs('Manifest')"
    checks = [f"equals({result}['[Tests]'],10)",
              f"equals(coalesce({result}['[Failed]'],0),0)",
              f"equals({result}['[VerifiedSources]'],2)",
              f"equals({m}['BatchID'],'{batch}')", f"equals({m}['SchemaVersion'],1)",
              f"equals({m}['Status'],'committed')", f"equals(length({m}['Sources']),2)",
              f"equals({m}['Validation']['Keysets'],true)",
              f"equals({m}['Validation']['Metadata'],true)",
              f"equals({m}['Validation']['RefreshGeneration'],true)"]
    for i, source, count, pages in [(0, 'PubMed', 1261, 39), (1, 'DORA', 709, 8)]:
        s = f"{m}['Sources'][{i}]"
        publication_table, publication_pages, chunk_table, key = (
            ('PubMedPublications', 13, 'PubMedMetadataChunks', 'PMID') if source == 'PubMed'
            else ('DoraPublications', 8, 'DoraMetadataChunks', 'DORAKey'))
        checks += [f"equals({s}['Source'],'{source}')", f"equals({s}['ExpectedRecords'],{count})",
                   f"equals({s}['PublicationTable'],'{publication_table}')",
                   f"equals({s}['PublicationPageCount'],{publication_pages})",
                   f"equals({s}['ChunkTable'],'{chunk_table}')", f"equals({s}['KeyColumn'],'{key}')",
                   f"equals({s}['PageCount'],{pages})", f"equals(length({s}['ExpectedKeys']),{count})",
                   f"equals(length(union({s}['ExpectedKeys'],{s}['ExpectedKeys'])),{count})"]
    # Power Automate expressions are dynamically typed here.  Failure markers
    # are deliberately text; wrapping them in int() causes the flow to fail
    # while evaluating the failure branch instead of returning a diagnostic.
    actions['Require_validation'] = compose("@if(and(" + ','.join(checks) + "),'VERIFIED','COMMIT_VALIDATION_FAILED')", 'Manifest')
    write = copy.deepcopy(old['Create_file'])
    write['runAfter'] = after('Require_validation')
    write['inputs']['parameters'] = {'folderPath': '/CHHHS Research System - DEV/01 Source archive',
        'name': f'commit-{batch}.json', 'body': "@string(outputs('Manifest'))"}
    actions['Create_file'] = write
    actions['Get_file_content_using_path'] = copy.deepcopy(old['Get_file_content_using_path'])
    actions['Verify_commit_readback'] = compose(
        "@if(equals(base64ToString(body('Get_file_content_using_path')['$content']),string(outputs('Manifest'))),'COMMIT_READBACK_VERIFIED','COMMIT_READBACK_FAILED')",
        'Get_file_content_using_path')
    definition['actions'] = actions
    title = 'CHHHS Publications - DEV validated first history commit'
    document['properties']['displayName'] = title
    files[name] = json.dumps(document).encode()
    manifest = json.loads(files['manifest.json'])
    manifest['details']['displayName'] = title
    for resource in manifest['resources'].values():
        if resource['type'] == 'Microsoft.Flow/flows':
            resource['suggestedCreationType'] = 'New'
            resource['details']['displayName'] = title
    files['manifest.json'] = json.dumps(manifest).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, content in files.items():
            z.writestr(n, content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    build(args.baseline, args.output, args.batch)
    print('Prepared manual bootstrap package; native import and validation pending.')
