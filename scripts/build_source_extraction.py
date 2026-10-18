"""Generate bounded native DAX extraction queries from staged TMDL columns.

These are Power Automate query inputs, not a deployed flow. Compound cursors
keep chunk/author boundaries safe; consumers must reject duplicate tuples.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'PubMedPublications': ['PMID'],
    'DoraPublications': ['DORAKey'],
    'PubMedMetadataChunks': ['PMID', 'ChunkIndex'],
    'DoraMetadataChunks': ['DORAKey', 'ChunkIndex'],
    'PubMedAuthorEvidence': ['PMID', 'AuthorIndex', 'AffiliationIndex'],
}


def build():
    model = (ROOT / 'config/native-ingestion.tmdl').read_text()
    for table, keys in SOURCES.items():
        body = model.split('\ttable ' + table + '\n', 1)[1].split('\ttable ', 1)[0]
        fields = re.findall(r'^\t\tcolumn (\w+)$', body, re.M)
        if not fields or any(key not in fields for key in keys):
            raise ValueError('Missing extraction columns: ' + table)
        variables = '\n'.join(f'VAR After{i} = ' + ('""' if i == 0 else '-1') for i in range(len(keys)))
        comparisons = []
        for i, key in enumerate(keys):
            equal = [f'{table}[{prior}] = After{j}' for j, prior in enumerate(keys[:i])]
            comparisons.append('(' + ' && '.join(equal + [f'{table}[{key}] > After{i}']) + ')')
        order = ', '.join(f'{table}[{key}], ASC' for key in keys)
        columns = ',\n'.join(f'    "{field}", {table}[{field}]' for field in fields)
        query = f'''// Run only against a verified frozen staging refresh. Include nulls in the response.
// Replace After variables with the last accepted tuple; double quotes in text cursors.
// Reject all response errors and duplicate tuples; do not advance on partial results.
EVALUATE
{variables}
VAR PageSize = 100
RETURN
SELECTCOLUMNS(
    TOPN(PageSize, FILTER({table}, {' || '.join(comparisons)}), {order}),
{columns}
)
ORDER BY {', '.join('[' + key + ']' for key in keys)}
'''
        (ROOT / 'config' / f'source-{table}-page.dax').write_text(query)
    print('Generated five source extraction queries; native execution pending.')


if __name__ == '__main__':
    build()
