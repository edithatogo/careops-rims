"""Build a manual staging flow from a verified Power Automate UI export.

Output contains private connection references and must remain under private/.
Pages are uncommitted staging data: no registry or reporting reader may consume
these until source-key, metadata and refresh-generation validation accepts them.
"""
import argparse
import copy
import json
import re
import zipfile
from pathlib import Path

from build_source_extraction import ROOT, SOURCES


def after(name):
    return {name: ['Succeeded']}


def compose(value, previous=None):
    return {'type': 'Compose', 'inputs': value, 'runAfter': after(previous) if previous else {}}


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def page_expression(table, keys):
    query = (ROOT / 'config' / f'source-{table}-page.dax').read_text()
    pieces = []
    start = 0
    matches = list(re.finditer(r'VAR After(\d+) = (?:""|-1)', query))
    if [int(match[1]) for match in matches] != list(range(len(keys))):
        raise ValueError('Cursor template indexes changed: ' + table)
    for match in matches:
        i = int(match[1])
        pieces.append(literal(query[start:match.start()] + f'VAR After{i} = '))
        cursor = f"variables('{table}_cursor_{i}')"
        pieces.append(f"concat('\"',replace({cursor},'\"','\"\"'),'\"')" if i == 0 else f'string({cursor})')
        start = match.end()
    pieces.append(literal(query[start:]))
    if len(pieces) != 2 * len(keys) + 1:
        raise ValueError('Cursor template changed: ' + table)
    return '@concat(' + ','.join(pieces) + ')'


def build_package(source, output):
    output = output.resolve()
    if not output.is_relative_to((ROOT / 'private').resolve()):
        raise ValueError('Native package must be written under ignored private/.')
    with zipfile.ZipFile(source) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    name = next(n for n in files if n.endswith('/definition.json'))
    document = json.loads(files[name])
    definition = document['properties']['definition']
    if list(definition['triggers']) != ['manual']:
        raise ValueError('Require the verified manual-only baseline.')
    baseline = definition['actions']
    query_template = baseline['Run_a_query_against_a_dataset']
    write_template = baseline['Create_file']
    read_template = baseline['Get_file_content_using_path']
    if read_template['inputs']['host']['operationId'] != 'GetFileContentByPath':
        raise ValueError('Unverified readback operation.')
    actions = {'Run_a_query_against_a_dataset': copy.deepcopy(query_template)}
    actions['Batch'] = compose('@guid()', 'Run_a_query_against_a_dataset')
    variables = []
    for table, keys in SOURCES.items():
        variables.extend([{'name': table + '_page', 'type': 'integer', 'value': 0},
                          {'name': table + '_count', 'type': 'integer', 'value': 0},
                          {'name': table + '_keys', 'type': 'array', 'value': []},
                          {'name': table + '_done', 'type': 'boolean', 'value': False}])
        variables.extend({'name': f'{table}_cursor_{i}', 'type': 'string' if i == 0 else 'integer',
                          'value': '' if i == 0 else -1} for i in range(len(keys)))
    previous = 'Batch'
    for variable in variables:
        initialize_name = 'Initialize_' + variable['name']
        actions[initialize_name] = {'type': 'InitializeVariable', 'inputs': {'variables': [variable]}, 'runAfter': after(previous)}
        previous = initialize_name
    for table, keys in SOURCES.items():
        prefix = table + '_'
        expected_name = prefix + 'Expected_keys'
        expected = copy.deepcopy(query_template)
        expected['runAfter'] = after(previous)
        columns = ','.join(f'"{key}", {table}[{key}]' for key in keys)
        expected['inputs']['parameters']['specification/query'] = f'EVALUATE SELECTCOLUMNS({table},{columns})'
        actions[expected_name] = expected
        previous = expected_name
        query_name = prefix + 'Query'
        query = copy.deepcopy(query_template)
        query['runAfter'] = {}
        query['inputs']['parameters']['specification/query'] = page_expression(table, keys)
        inner = {query_name: query}
        # Fail the action rather than silently substituting [] for a missing result.
        rows_name = prefix + 'Rows'
        inner[rows_name] = compose(f"@body('{query_name}')['results'][0]['tables'][0]['rows']", query_name)
        write_name, read_name = prefix + 'Write', prefix + 'Read'
        write = copy.deepcopy(write_template)
        write['runAfter'] = {}
        write['inputs']['parameters'].update({
            'folderPath': '/CHHHS Research System - DEV/01 Source archive',
            'name': f"@concat('uncommitted-',outputs('Batch'),'-{table}-',string(variables('{table}_page')),'.json')",
            'body': f"@string(outputs('{rows_name}'))"})
        read = copy.deepcopy(read_template)
        read['runAfter'] = after(write_name)
        read['inputs']['parameters']['path'] = f"@body('{write_name}')['Path']"
        check_name = prefix + 'Require_exact_readback'
        # int(non-numeric text) intentionally fails a Compose action on mismatch.
        check = compose(f"@if(equals(base64ToString(body('{read_name}')['$content']),string(outputs('{rows_name}'))),'VERIFIED',int('READBACK_MISMATCH'))", read_name)
        page_actions = {write_name: write, read_name: read, check_name: check}
        select_name = prefix + 'Page_keys'
        page_actions[select_name] = {'type': 'Select', 'inputs': {
            'from': f"@outputs('{rows_name}')", 'select': {
                f'[{key}]': f"@item()['[{key}]']" for key in keys}}, 'runAfter': after(check_name)}
        merge_name = prefix + 'Merged_keys'
        page_actions[merge_name] = compose(f"@union(variables('{table}_keys'),body('{select_name}'))", select_name)
        set_name = prefix + 'Store_keys'
        page_actions[set_name] = {'type': 'SetVariable', 'inputs': {
            'name': table + '_keys', 'value': f"@outputs('{merge_name}')"}, 'runAfter': after(merge_name)}
        count_name = prefix + 'Count_rows'
        page_actions[count_name] = {'type': 'IncrementVariable', 'inputs': {
            'name': table + '_count', 'value': f"@length(outputs('{rows_name}'))"}, 'runAfter': after(set_name)}
        last = count_name
        for i, key in enumerate(keys):
            cursor_name = prefix + f'Advance_{i}'
            page_actions[cursor_name] = {'type': 'SetVariable', 'inputs': {
                'name': f'{table}_cursor_{i}', 'value': f"@last(outputs('{rows_name}'))['[{key}]']"}, 'runAfter': after(last)}
            last = cursor_name
        page_actions[prefix + 'Next_page'] = {'type': 'IncrementVariable', 'inputs': {'name': table + '_page', 'value': 1}, 'runAfter': after(last)}
        inner[prefix + 'Has_rows'] = {'type': 'If', 'expression': {'greater': [f"@length(outputs('{rows_name}'))", 0]},
            'actions': page_actions, 'else': {'actions': {prefix + 'Done': {'type': 'SetVariable',
            'inputs': {'name': table + '_done', 'value': True}, 'runAfter': {}}}}, 'runAfter': after(rows_name)}
        loop_name = prefix + 'Pages'
        actions[loop_name] = {'type': 'Until', 'expression': f"@equals(variables('{table}_done'),true)",
            'limit': {'count': 5000, 'timeout': 'PT6H'}, 'actions': inner, 'runAfter': after(previous)}
        final_name = prefix + 'Final_keys'
        final = copy.deepcopy(expected)
        final['runAfter'] = after(loop_name)
        actions[final_name] = final
        expected_rows = f"body('{expected_name}')['results'][0]['tables'][0]['rows']"
        final_rows = f"body('{final_name}')['results'][0]['tables'][0]['rows']"
        stored_keys = f"variables('{table}_keys')"
        # Equal lengths and full intersections prove exact sets and no duplicates.
        checks = [f"equals(variables('{table}_done'),true)",
                  f"equals(variables('{table}_count'),length({expected_rows}))",
                  f"equals(length({stored_keys}),length({expected_rows}))",
                  f"equals(length(intersection({stored_keys},{expected_rows})),length({expected_rows}))",
                  f"equals(length({final_rows}),length({expected_rows}))",
                  f"equals(length(intersection({final_rows},{expected_rows})),length({expected_rows}))"]
        acceptance_name = prefix + 'Require_complete_keyset'
        actions[acceptance_name] = compose("@if(and(" + ','.join(checks) + "),'KEYSET_VERIFIED',int('SOURCE_KEYSET_MISMATCH'))", final_name)
        previous = acceptance_name
    # Deliberately no success/commit manifest. Exhaustion, native acceptance and
    # refresh-generation validation must pass before history promotion.
    actions['Staging_only'] = compose('UNCOMMITTED: keysets validated; refresh-generation and metadata validation required before registry promotion.', previous)
    definition['actions'] = actions
    files[name] = json.dumps(document, separators=(',', ':')).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return len(actions)




# Portable validation helpers from the qualified source snapshot.
from uuid import UUID

def _tmdl_table_projection(model, table):
    """Read ordered column-name/sourceColumn pairs for one native TMDL table."""
    table_match = re.search(rf'(?m)^\ttable {re.escape(table)}\s*$', model)
    if not table_match:
        raise ValueError('Missing native TMDL table: ' + table)
    next_table = re.search(r'(?m)^\ttable ', model[table_match.end():])
    body_end = table_match.end() + next_table.start() if next_table else len(model)
    body = model[table_match.end():body_end]
    column_matches = list(re.finditer(
        r'(?m)^\t\tcolumn ([^\n]+)\n(.*?)(?=^\t\t(?:column |partition |annotation )|\Z)',
        body, re.S))
    projection = []
    for match in column_matches:
        alias = match.group(1).strip().strip("'")
        source_match = re.search(r'(?m)^\t\t\tsourceColumn: (.+?)\s*$', match.group(2))
        if not source_match:
            raise ValueError(f'Native TMDL column lacks sourceColumn: {table}.{alias}')
        source_column = source_match.group(1).strip().strip("'")
        if not alias or not source_column:
            raise ValueError(f'Invalid native TMDL projection: {table}.{alias}')
        projection.append((alias, source_column))
    if not projection:
        raise ValueError('Native TMDL table has no columns: ' + table)
    return projection

def _selectcolumns_arguments(query):
    """Return top-level SELECTCOLUMNS arguments, respecting DAX strings/parens."""
    match = re.search(r'\bSELECTCOLUMNS\s*\(', query, re.I)
    if not match:
        raise ValueError('Page query has no SELECTCOLUMNS projection.')
    start = match.end()
    depth = 1
    in_string = False
    index = start
    while index < len(query):
        char = query[index]
        if in_string:
            if char == '"':
                if index + 1 < len(query) and query[index + 1] == '"':
                    index += 2
                    continue
                in_string = False
        elif char == '"':
            in_string = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                body = query[start:index]
                break
        index += 1
    else:
        raise ValueError('Unterminated SELECTCOLUMNS projection.')

    arguments = []
    depth = 0
    in_string = False
    token_start = 0
    index = 0
    while index < len(body):
        char = body[index]
        if in_string:
            if char == '"':
                if index + 1 < len(body) and body[index + 1] == '"':
                    index += 2
                    continue
                in_string = False
        elif char == '"':
            in_string = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                raise ValueError('Malformed SELECTCOLUMNS projection.')
        elif char == ',' and depth == 0:
            arguments.append(body[token_start:index].strip())
            token_start = index + 1
        index += 1
    arguments.append(body[token_start:].strip())
    if in_string or depth != 0:
        raise ValueError('Malformed SELECTCOLUMNS projection.')
    return arguments

def validate_page_projection(table, query, model):
    """Require the page projection to match every ordered TMDL field exactly."""
    expected = _tmdl_table_projection(model, table)
    arguments = _selectcolumns_arguments(query)
    if len(arguments) < 3 or (len(arguments) - 1) % 2:
        raise ValueError(f'Invalid SELECTCOLUMNS projection shape: {table}')
    actual = []
    for alias_expression, source_expression in zip(arguments[1::2], arguments[2::2]):
        alias_match = re.fullmatch(r'"((?:[^"]|"")*)"', alias_expression)
        source_match = re.fullmatch(r'([A-Za-z_]\w*)\s*\[([^\]]+)\]', source_expression)
        if not alias_match or not source_match:
            raise ValueError(f'Invalid page projection expression: {table}')
        alias = alias_match.group(1).replace('""', '"')
        source_table, source_column = source_match.groups()
        if source_table != table:
            raise ValueError(f'Page projection uses a different table: {table}.{alias}')
        actual.append((alias, source_column.strip().strip("'")))
    if actual != expected:
        raise ValueError(f'Page projection differs from native TMDL columns: {table}')

def validate_configured_page_projection(table):
    model = (ROOT / 'config' / 'native-ingestion.tmdl').read_text()
    query = (ROOT / 'config' / f'source-{table}-page.dax').read_text()
    validate_page_projection(table, query, model)

def build_definition(document, *, tables=None, batch=None):
    """Compile staging only; fixed batches refuse conflicts instead of rewriting.

    The caller qualifies connections/model/destination before native deployment.
    This function neither connects to the tenant nor emits a commit marker.
    """
    selected = list(SOURCES) if tables is None else list(tables)
    if not selected or len(selected) != len(set(selected)) or any(table not in SOURCES for table in selected):
        raise ValueError('Nonempty unique supported source tables required.')
    if batch is not None:
        if not isinstance(batch, str) or str(UUID(batch)) != batch:
            raise ValueError('Fixed batch must be a canonical UUID.')
    selected_sources = {table: SOURCES[table] for table in selected}
    for table in selected_sources:
        validate_configured_page_projection(table)
    document = copy.deepcopy(document)
    definition = document['properties']['definition']
    if list(definition['triggers']) != ['manual']:
        raise ValueError('Require the verified manual-only baseline.')
    baseline = definition['actions']
    queries = [action for action in baseline.values()
               if isinstance(action.get('inputs'), dict)
               and action['inputs'].get('host', {}).get('operationId') == 'ExecuteDatasetQuery']
    if len(queries) != 1:
        raise ValueError('Require exactly one qualified Power BI query template.')
    query_template = queries[0]
    write_template = baseline['Create_file']
    read_template = baseline['Get_file_content_using_path']
    if read_template['inputs']['host']['operationId'] != 'GetFileContentByPath':
        raise ValueError('Unverified readback operation.')
    if write_template['inputs']['host']['operationId'] != 'CreateFile':
        raise ValueError('Unverified file creation operation.')
    actions = {'Run_a_query_against_a_dataset': copy.deepcopy(query_template)}
    actions['Batch'] = compose(batch if batch is not None else '@guid()', 'Run_a_query_against_a_dataset')
    variables = []
    for table, keys in selected_sources.items():
        variables.extend([{'name': table + '_page', 'type': 'integer', 'value': 0},
                          {'name': table + '_count', 'type': 'integer', 'value': 0},
                          {'name': table + '_keys', 'type': 'array', 'value': []},
                          {'name': table + '_done', 'type': 'boolean', 'value': False}])
        variables.extend({'name': f'{table}_cursor_{i}', 'type': 'string' if i == 0 else 'integer',
                          'value': '' if i == 0 else -1} for i in range(len(keys)))
    previous = 'Batch'
    for variable in variables:
        initialize_name = 'Initialize_' + variable['name']
        actions[initialize_name] = {'type': 'InitializeVariable', 'inputs': {'variables': [variable]}, 'runAfter': after(previous)}
        previous = initialize_name
    for table, keys in selected_sources.items():
        prefix = table + '_'
        expected_name = prefix + 'Expected_keys'
        expected = copy.deepcopy(query_template)
        expected['runAfter'] = after(previous)
        columns = ','.join(f'"{key}", {table}[{key}]' for key in keys)
        expected['inputs']['parameters']['specification/query'] = f'EVALUATE SELECTCOLUMNS({table},{columns})'
        actions[expected_name] = expected
        previous = expected_name
        query_name = prefix + 'Query'
        query = copy.deepcopy(query_template)
        query['runAfter'] = {}
        query['inputs']['parameters']['specification/query'] = page_expression(table, keys)
        inner = {query_name: query}
        # Fail the action rather than silently substituting [] for a missing result.
        rows_name = prefix + 'Rows'
        inner[rows_name] = compose(f"@body('{query_name}')['results'][0]['tables'][0]['rows']", query_name)
        write_name, read_name = prefix + 'Write', prefix + 'Read'
        write = copy.deepcopy(write_template)
        write['runAfter'] = {}
        write['inputs']['parameters'].update({
            'folderPath': '/CHHHS Research System - DEV/01 Source archive',
            'name': f"@concat('uncommitted-',outputs('Batch'),'-{table}-',string(variables('{table}_page')),'.json')",
            'body': f"@string(outputs('{rows_name}'))"})
        read = copy.deepcopy(read_template)
        read['runAfter'] = after(write_name)
        read['inputs']['parameters']['path'] = f"@body('{write_name}')['Path']"
        check_name = prefix + 'Require_exact_readback'
        # int(non-numeric text) intentionally fails a Compose action on mismatch.
        check = compose(f"@if(equals(base64ToString(body('{read_name}')['$content']),string(outputs('{rows_name}'))),'VERIFIED',int('READBACK_MISMATCH'))", read_name)
        page_actions = {write_name: write, read_name: read, check_name: check}
        if batch is not None:
            # A fixed batch can be replayed only against identical stored bytes.
            # Only explicit absence permits creation; errors never mean absent.
            # This is a single-writer guard, not a cross-writer atomic guarantee.
            existing_name, exists_name = prefix + 'Existing', prefix + 'Exists'
            path = "@concat('/CHHHS Research System - DEV/01 Source archive/'," + write['inputs']['parameters']['name'][1:] + ")"
            existing = copy.deepcopy(read_template)
            existing['runAfter'] = {}
            existing['inputs']['parameters']['path'] = path
            require_missing = prefix + 'Require_missing'
            write['runAfter'] = after(require_missing)
            read['runAfter'] = after(exists_name)
            read['inputs']['parameters']['path'] = path
            page_actions = {
                existing_name: existing,
                exists_name: {
                    'type': 'If', 'expression': {'equals': [f"@outputs('{existing_name}')?['statusCode']", 200]},
                    'actions': {prefix + 'Require_existing_match': compose(
                        f"@if(equals(base64ToString(body('{existing_name}')['$content']),string(outputs('{rows_name}'))),'REPLAY_VERIFIED',int('STAGING_CONFLICT'))")},
                    'else': {'actions': {
                        require_missing: compose(f"@if(equals(outputs('{existing_name}')?['statusCode'],404),'ABSENT',int('STAGING_READ_FAILED'))"),
                        write_name: write}},
                    'runAfter': {existing_name: ['Succeeded', 'Failed']}},
                read_name: read, check_name: check}
        select_name = prefix + 'Page_keys'
        page_actions[select_name] = {'type': 'Select', 'inputs': {
            'from': f"@outputs('{rows_name}')", 'select': {
                f'[{key}]': f"@item()['[{key}]']" for key in keys}}, 'runAfter': after(check_name)}
        merge_name = prefix + 'Merged_keys'
        page_actions[merge_name] = compose(f"@union(variables('{table}_keys'),body('{select_name}'))", select_name)
        set_name = prefix + 'Store_keys'
        page_actions[set_name] = {'type': 'SetVariable', 'inputs': {
            'name': table + '_keys', 'value': f"@outputs('{merge_name}')"}, 'runAfter': after(merge_name)}
        count_name = prefix + 'Count_rows'
        page_actions[count_name] = {'type': 'IncrementVariable', 'inputs': {
            'name': table + '_count', 'value': f"@length(outputs('{rows_name}'))"}, 'runAfter': after(set_name)}
        last = count_name
        for i, key in enumerate(keys):
            cursor_name = prefix + f'Advance_{i}'
            page_actions[cursor_name] = {'type': 'SetVariable', 'inputs': {
                'name': f'{table}_cursor_{i}', 'value': f"@last(outputs('{rows_name}'))['[{key}]']"}, 'runAfter': after(last)}
            last = cursor_name
        page_actions[prefix + 'Next_page'] = {'type': 'IncrementVariable', 'inputs': {'name': table + '_page', 'value': 1}, 'runAfter': after(last)}
        inner[prefix + 'Has_rows'] = {'type': 'If', 'expression': {'greater': [f"@length(outputs('{rows_name}'))", 0]},
            'actions': page_actions, 'else': {'actions': {prefix + 'Done': {'type': 'SetVariable',
            'inputs': {'name': table + '_done', 'value': True}, 'runAfter': {}}}}, 'runAfter': after(rows_name)}
        loop_name = prefix + 'Pages'
        actions[loop_name] = {'type': 'Until', 'expression': f"@equals(variables('{table}_done'),true)",
            'limit': {'count': 5000, 'timeout': 'PT6H'}, 'actions': inner, 'runAfter': after(previous)}
        final_name = prefix + 'Final_keys'
        final = copy.deepcopy(expected)
        final['runAfter'] = after(loop_name)
        actions[final_name] = final
        expected_rows = f"body('{expected_name}')['results'][0]['tables'][0]['rows']"
        final_rows = f"body('{final_name}')['results'][0]['tables'][0]['rows']"
        stored_keys = f"variables('{table}_keys')"
        # Equal lengths and full intersections prove exact sets and no duplicates.
        checks = [f"equals(variables('{table}_done'),true)",
                  f"equals(variables('{table}_count'),length({expected_rows}))",
                  f"equals(length({stored_keys}),length({expected_rows}))",
                  f"equals(length(intersection({stored_keys},{expected_rows})),length({expected_rows}))",
                  f"equals(length({final_rows}),length({expected_rows}))",
                  f"equals(length(intersection({final_rows},{expected_rows})),length({expected_rows}))"]
        acceptance_name = prefix + 'Require_complete_keyset'
        actions[acceptance_name] = compose("@if(and(" + ','.join(checks) + "),'KEYSET_VERIFIED',int('SOURCE_KEYSET_MISMATCH'))", final_name)
        previous = acceptance_name
    # Deliberately no success/commit manifest. Exhaustion, native acceptance and
    # refresh-generation validation must pass before history promotion.
    actions['Staging_only'] = compose('UNCOMMITTED: keysets validated; refresh-generation and metadata validation required before registry promotion.', previous)
    definition['actions'] = actions
    return document

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(f'Built {build_package(args.baseline, args.output)} top-level actions; native import and validation pending.')
