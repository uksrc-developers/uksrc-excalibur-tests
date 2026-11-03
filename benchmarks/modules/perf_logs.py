# moved from utils.py to separate the pandas dependency
from .utils import *

import pandas as pd

import sys
import json
import uuid
import requests
from typing import AnyStr, Dict
from requests.auth import HTTPBasicAuth

def read_perflog(path):
    """ Return a pandas dataframe from a ReFrame performance log.

        Args:
            path: str, path to log file.

        NB: This currently depends on having a non-default handlers_perflog.filelog.format in reframe's configuration. See code.

        The returned dataframe will have columns for:
            - all keys returned by `parse_path_metadata()`
            - all fields in a performance log record, noting that:
              - 'completion_time' is converted to a `datetime.datetime`
              - 'tags' is split on commas into a list of strs
            - 'perf_var' and 'perf_value', derived from 'perf_info' field
            - <key> for any tags of the format "<key>=<value>", with values converted to int or float if possible
    """

    # NB:
    # b/c perflog prefix is '%(check_system)s/%(check_partition)s/%(check_environ)s/%(check_name)s'
    # we know that this is unique for this combo - as it was for results
    records = []
    meta = parse_path_metadata(path)

    with open(path) as f:

        try:

            for line in f:

                # turn the line into a dict so we can access it:
                line = line.strip()
                # TODO: read this from reframe-settings handlers_perflog.filelog.format? (is adapted tho)
                LOG_FIELDS = 'completion_time,reframe,info,jobid,perf_data,perf_unit,perf_ref,tags'.split(',')
                record = meta.copy()
                fields = dict(zip(LOG_FIELDS, line.split('|')))
                record.update(fields) # allows this to override metadata

                # process values:
                perf_var, perf_value = record['perf_data'].split('=')
                record['perf_var'] = perf_var
                try:
                    record['perf_value'] = float(perf_value)
                except ValueError:
                    record['perf_value'] = perf_value
                record['completion_time'] = datetime.datetime.fromisoformat(record['completion_time'])
                record['jobid'] = record['jobid'].split('=')[-1] # original: "jobid=2378"
                non_kv_tags = []
                tags = record['tags'].split(',')
                for tag in tags:
                    if '=' in tag:
                        k, v = tag.split('=')
                        for conv in (int, float):
                            try:
                                v = conv(v)
                            except ValueError:
                                pass
                            else:
                                break
                        record[k] = v
                record['tags'] = tags
                records.append(record)
        except Exception as e:
            e.args = (e.args[0] + ': during processing %s' % path,) + e.args[1:]
            raise

    return pd.DataFrame.from_records(records)

def load_perf_logs(root='.', test=None, ext='.log', last=False):
    """ Convenience wrapper around read_perflog().

        Args:
            root: str, path to root of tree containing perf logs
            test: str, shell-style glob pattern matched against last directory component to restrict loaded logs, or None to load all in tree
            ext: str, only load logs from files with this extension
            last: bool, True to only return the most-recent record for each system/partition/enviroment/testname/perf_var combination.

        Returns a single pandas.dataframe concatenated from all loaded logs, or None if no logs exist.
    """
    perf_logs = find_run_outputs(root, test, ext)
    perf_records = []
    for path in perf_logs:
        records = read_perflog(path)
        perf_records.append(records)
    if len(perf_records) == 0:
        return None
    perf_records = pd.concat(perf_records).reset_index(drop=True)

    if last:
        perf_records = perf_records.sort_index().groupby(['sysname', 'partition', 'environ', 'testname', 'perf_var']).tail(1)

    return perf_records

def tabulate_last_perf(test, index, perf_var, root='../../perflogs'):
    """ Retrieve last perf_log entry for each system/partition/environment.

        Args:
            test: str, shell-style glob pattern matched against last directory component to restrict loaded logs, or None to load all in tree
            index: str, name of perf_log parameter to use as index (see `read_perflog()` for valid names)
            perf_var: str, name of perf_var to extract
            root: str, path to root of tree containing perf logs of interest - default assumes this is called from an `apps/<application>/` directory

        Returns a dataframe with columns:
            case: TODO:

    """

    df = load_perf_logs(root=root, test=test, ext='.log', last=True)
    if df is None: # no data
        return None

    # filter to rows for correct perf_var:
    df = df.loc[df['perf_var'] == perf_var]

    # keep only the LAST record in each system/partition/environment/xvar
    df = df.sort_index().groupby(['sysname', 'partition', 'environ', index]).tail(1)

    # Add "case" column from combined system/partition:
    df['case'] = df[['sysname', 'partition']].agg(':'.join, axis=1)

    # reshape to wide table:
    df = df.pivot(index=index, columns='case', values='perf_value')

    return df

#
def iter_tables(node):
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if cur.get("type") == "table":
                yield cur
            for child in cur.get("content", []) or []:
                stack.append(child)
        elif isinstance(cur, list):
            stack.extend(cur)

def get_table_fragment_name_and_id(table_node):
    name = None
    local_id = None
    for m in table_node.get("marks", []) or []:
        if m.get("type") == "fragment":
            attrs = m.get("attrs") or {}
            name = attrs.get("name") or name
            local_id = attrs.get("localId") or local_id
    return name, local_id

def table_cell_text(text: str):
    return {
        "type": "tableCell",
        "attrs": {"colspan": 1, "rowspan": 1},
        "content": [{"type": "paragraph", "content": ([{"type": "text", "text": text}] if text else "")}],
    }

def count_columns(table_node: dict) -> int:
    rows = table_node.get("content") or []
    if not rows:
        return 0
    first_row = rows[0]
    return len(first_row.get("content") or [])

def build_new_table(table_name: str, content: Dict) -> dict:
    table_node = {
        "type": "table",
        "attrs": {
            'layout': 'align-start',
            'width': 941.0,
        },
        "marks": [
            {
                'type': 'fragment',
                'attrs': {
                    "name": table_name,
                    "localId": str(uuid.uuid4())
                }
            }
        ],
        "content": [
            {
                "type": "tableRow",
                "content": []
            },
            {
                "type": "tableRow",
                "content": []
            }
        ]
    }
    for k, v in content.items():
        table_node["content"][0]["content"] += [{
            'type': 'tableHeader',
            'attrs': {
                'colspan': 1,
                'rowspan': 1
            },
            'content': [
                {
                    'type': 'paragraph',
                    'content': [
                        {
                            'text': k,
                            'type': 'text',
                            'marks': [
                                {
                                    'type': 'strong'
                                }
                            ]
                        }
                    ]
                }
            ]
        }]
        table_node["content"][1]["content"] += [{
            'type': 'tableCell',
            'attrs': {
                'colspan': 1,
                'rowspan': 1
            },
            'content': [
                {
                    'type': 'paragraph',
                    'content': [
                        {
                            'text': v,
                            'type': 'text',
                        }
                    ]
                }
            ]
        }]
    return table_node

def send_to_table(site: AnyStr, space_id: AnyStr, email: AnyStr, api_token: AnyStr, table_name: AnyStr, content: Dict):
    assert api_token.strip() == api_token, "API token has leading/trailing whitespace/newlines"
    url = f"{site}/wiki/api/v2/pages/{space_id}?body-format=atlas_doc_format"
    response = requests.get(
        url,
        headers={"Accept": "application/json", "User-Agent": "step1-list-tables/0.1"},
        auth=HTTPBasicAuth(email, api_token),
        timeout=30,
    )
    if response.status_code != 200:
        print(response.text[:800])
        sys.exit(2)
    page = response.json()
    title = page.get("title")
    version_num = (page.get("version") or {}).get("number") or 0
    value = page.get("body", {}).get("atlas_doc_format", {}).get("value")
    adf = json.loads(value) if isinstance(value, str) else value
    table_of_interest = None
    for i, tbl in enumerate(iter_tables(adf), start=1):
        name, local_id = get_table_fragment_name_and_id(tbl)
        if name == table_name:
            table_of_interest = tbl
            break

    if not bool(table_of_interest):
        new_table = build_new_table(table_name, content)
        # PUT back with version+1 (ADF must be stringified in v2 API)
        adf["content"].append({
            "type": "paragraph",
            'content': [
                {
                    'text': f'{table_name}',
                    'type': 'text'
                }
            ],
            'marks': [
                {
                    'type': 'strong'
                }
            ]
        })
        adf["content"].append(new_table)
    else:
        ncols = count_columns(table_of_interest)
        if ncols != len(content):
            raise ValueError(f"{ncols} Columns found, but content of {content}, does not match.")
        new_cells = [table_cell_text(content_text) for content_text in content.values()]
        new_row = {"type": "tableRow", "content": new_cells}
        table_of_interest.setdefault("content", []).append(new_row)

    # PUT back with version+1 (ADF must be stringified in v2 API)
    put_url = f"{site}/wiki/api/v2/pages/{space_id}"
    payload = {
        "id": space_id,
        "status": "current",
        "title": title,
        "version": {"number": version_num + 1},
        "body": {"atlas_doc_format": {"value": json.dumps(adf), "representation": "atlas_doc_format"}},
    }

    pr = requests.put(
        put_url,
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "step2-append-row/0.1"},
        auth=HTTPBasicAuth(email, api_token),
        data=json.dumps(payload),
        timeout=30,
    )

    if pr.status_code not in (200, 202):
        print(pr.text[:1000])
        sys.exit(4)
    return
#
