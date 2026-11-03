# moved from utils.py to separate the pandas dependency
from time import sleep

from .utils import *

import pandas as pd

import os, io, re
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from atlassian import Confluence
from bs4 import BeautifulSoup
from keystoneauth1 import session
from keystoneauth1.identity import v3
from swiftclient.client import Connection
import sqlite3

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

# Functions and class for handling, updating and reading a swift object store saved sql database using sqlite.
def get_database(
        container : str,
        db_file : str,
        sess : session.Session,
        os_options : dict,
        local_db_file : str = None):
    if local_db_file is None:
        local_db_file = db_file
    conn = Connection(
        session=sess,
        os_options=os_options
    )
    try:
        _, obj_contents = conn.get_object(container, db_file)
        with open(local_db_file, 'wb') as local_file:
            local_file.write(obj_contents)
    except Exception as e:
        print(f"Unable to GET Database: {e}")
        print(f"os_options = {os_options}")
        print(f"container={container}")
        print(f"db_file={db_file}")
    finally:
        conn.close()
    sleep(1)

def put_database(
        container : str,
        db_file : str,
        sess : session.Session,
        os_options : dict,
        local_db_file : str = None):
    if local_db_file is None:
        local_db_file = db_file
    conn = Connection(
        session=sess,
        os_options=os_options
    )
    try:
        with open(local_db_file, 'rb') as local_file:
            conn.put_object(container, db_file, contents=local_file)
    except Exception as e:
        print(f"Unable to PUT Database: {e}")
        print(f"container={container}")
        print(f"db_file={db_file}")
    finally:
        conn.close()

class DatabaseConnection:
    def __init__(
            self,
            container: str,
            db_file: str,
            os_options: dict,
            read_only: bool = False
    ):
        self.container = container
        self.db_file = db_file
        self.os_options = os_options
        self.read_only = read_only

        self.auth = v3.ApplicationCredential(
            auth_url=os.environ.get('OS_AUTH_URL'),
            application_credential_id=os.environ.get('OS_APPLICATION_CREDENTIAL_ID'),
            application_credential_secret=os.environ.get('OS_APPLICATION_CREDENTIAL_SECRET')
        )
        self.sess = session.Session(auth=self.auth)

    def __enter__(self):
        try:
            get_database(container=self.container, db_file=self.db_file, sess=self.sess, os_options=self.os_options)
        except Exception as e:
            print(f"Error getting database: {e}")
            print(f"Treating {self.db_file} as new database on {self.container}")
        self.con = sqlite3.connect(self.db_file)
        self.cur = self.con.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.con.commit()
        self.con.close()
        if not self.read_only:
            try:
                put_database(container=self.container, db_file=self.db_file, sess=self.sess, os_options=self.os_options)
            except Exception as e:
                print(f"Error putting database: {e}")
        subprocess.run(f"rm -f ./{self.db_file}", shell=True)

# The following functions provide utilies for getting results from a swift object store sql database and sending
# results to a Confuence page.
def load_all_test_data(conn, cursor):
    """Load all data from all tables into a dictionary of DataFrames."""

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    data = {}
    for table in tables:
        if table != "sqlite_sequence":
            try:
                # Load entire table into DataFrame
                data[table] = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                data[table]['test_time_formated'] = pd.to_datetime(data[table]['TimeOfTest'])
            except Exception as e:
                print(f"Error loading table {table}: {e}")
                data[table] = pd.DataFrame()
    return data


def get_last_n_runs(df, n=2):
    """Filter DataFrame to last N runs (by date) per site."""
    # Rank runs per site by date

    extra_columns = [c for c in df.columns if c not in ["testID", "TimeOfTest", "SystemPartition", "ExecutionTime", "AvgTimeMS", "test_time_formated", 'run_rank']]

    df['run_rank'] = df.groupby(['SystemPartition'] + extra_columns)['TimeOfTest'].rank(method='dense', ascending=False)
    result = df[df['run_rank'] <= n].copy()
    result = result.sort_values(
        ['SystemPartition'] + extra_columns + ['TimeOfTest'],
        ascending=[True] + [True for i in range(len(extra_columns))] + [False]
    ).reset_index(drop=True)

    # Clean up helper columns
    result = result.drop(columns=['run_rank', 'testID', 'test_time_formated'])
    return result


def create_plot(data_frame, test_name):
    y_column = "AvgTimeMS" if "AvgTimeMS" in data_frame else "ExecutionTime"
    temp_daterange = data_frame['test_time_formated'].max() - data_frame['test_time_formated'].min()

    extra_cols = [c for c in data_frame.columns if c not in ["testID", "TimeOfTest", "SystemPartition", "ExecutionTime", "AvgTimeMS", "test_time_formated", 'run_rank']]
    group_cols = ["SystemPartition"] + extra_cols
    fig, ax = plt.subplots(figsize=(12, 6))
    skipped = 0
    attempt = 0
    if extra_cols:
        for name, group in data_frame.groupby(group_cols):
            attempt += 1
            label = " | ".join(str(v) for v in (name if isinstance(name, tuple) else (name,)))
            if len(group["test_time_formated"]) < 2:
                skipped += 1
            else:
                group.sort_values("test_time_formated").plot(
                    kind="line", x="test_time_formated", y=y_column, ax=ax, label=label
                )
        if skipped == attempt:

            return None

    else:
        if len(data_frame["test_time_formated"]) < 2:
            return None
        data_frame.sort_values("test_time_formated").plot(
            kind="line", x="test_time_formated", y=y_column, ax=ax
        )
        ax.legend().set_visible(False)

    ax.set_title(test_name)
    ax.set_ylim((data_frame[y_column].min()*0.975, data_frame[y_column].max()*1.025))
    ax.yaxis.set_label_text("Execution Time [s]")
    ax.xaxis.set_label_text("Time of Test")

    if temp_daterange > pd.Timedelta(days=90):
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m'))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m-%d'))

    return fig

def upload_plot(confluence_obj, page_id: str, filename: str, fig, table_name: str = None):
    # Save plot to buffer
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    # Upload attachment
    try:
        confluence_obj.attach_content(buf.read(), filename, content_type="image/png", page_id=page_id)
    except:
        pass

    # Embed in page if not already present
    page = confluence_obj.get_page_by_id(page_id, expand="body.storage")
    body = page["body"]["storage"]["value"]
    image_tag = f'<ac:image><ri:attachment ri:filename="{filename}" /></ac:image>'

    if f'ri:filename="{filename}"' not in body:
        if table_name:
            soup = BeautifulSoup(body, "html.parser")
            for table in soup.find_all("table"):
                first_th = table.find("th", colspan=True)
                if first_th and first_th.get_text(strip=True) == table_name:
                    table.insert_before(BeautifulSoup(image_tag, "html.parser"))
                    body = str(soup)
                    break
        else:
            body += image_tag

    try:
        confluence_obj.update_page(page_id, title=page["title"], body=body)
    except:
        pass

def update_table(page_body: str, table_name: str, content: list[dict]) -> str:
    soup = BeautifulSoup(page_body, "html.parser")

    for table in soup.find_all("table"):
        first_th = table.find("th", colspan=True)
        if first_th and first_th.get_text(strip=True) == table_name:
            rows = table.find_all("tr")
            # Keep first two rows (title + headers), remove the rest
            for row in rows[2:]:
                row.decompose()

            headers = [th.get_text(strip=True) for th in rows[1].find_all("th")]
            for entry in content:
                new_row = soup.new_tag("tr")
                for h in headers:
                    td = soup.new_tag("td")
                    td.string = str(entry.get(h, ""))
                    new_row.append(td)
                table.append(new_row)

            return str(soup)
    raise ValueError(f"Table '{table_name}' not found in page body")

def build_table(table_name: str, content: list[dict]) -> str:
    if not content:
        return ""

    headers = list(content[0].keys())
    col_count = len(headers)

    rows = [
        f'<tr><th colspan="{col_count}" style="text-align:center;">{table_name}</th></tr>',
        "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>",
    ]

    for row in content:
        rows.append("<tr>" + "".join(f"<td>{row.get(h, '')}</td>" for h in headers) + "</tr>")

    return "<table>" + "".join(rows) + "</table>"


def wrap_in_expand(title: str, inner_html: str) -> str:
    return (
        f'<ac:structured-macro ac:name="expand">'
        f'<ac:parameter ac:name="title">{title}</ac:parameter>'
        f'<ac:rich-text-body>{inner_html}</ac:rich-text-body>'
        f'</ac:structured-macro>'
    )

def parse_system_partition(system_partition):
    parts = system_partition.split(" - ")
    if parts[0] == "None":
        system = "Local Tests"
    else:
        system = parts[0].split("_", 1)[1]  # "runner_Cosma8" → "Cosma8"
    partition = parts[-1]                # last segment
    return system, partition


def update_confluence():
    with DatabaseConnection(
            container=os.environ.get('DB_CONTAINER', 'excalibur_tests_results'),
            db_file=os.environ.get('DB_FILE', 'reframe_results.db'),
            os_options={
                "interface": os.environ.get("OS_INTERFACE", "public"),
                "region_name": os.environ.get('OS_REGION_NAME', "RegionOne"),
            },
            read_only=True
    ) as db:
        full_dataframes = load_all_test_data(db.con, db.cur)

    confluence_obj = Confluence(url=os.environ.get('CONFLUENCE_SITE'), username=os.environ.get('CONFLUENCE_EMAIL'), password=os.environ.get('CONFLUENCE_API_TOKEN'))
    page = confluence_obj.get_page_by_id(os.environ.get('CONFLUENCE_SPACE_ID'), expand="body.storage")
    body = page["body"]["storage"]["value"]

    structure = {}
    for k, v in full_dataframes.items():
        if k == "sqlite_sequence":
            continue
        for sp in v["SystemPartition"].unique():
            system, partition = parse_system_partition(sp)
            system = "Local Tests" if system == "None" else system
            structure.setdefault(system, {}).setdefault(partition, []).append(
                (k, v[v["SystemPartition"] == sp])
            )

    for system in sorted(structure):
        system_inner = ""
        for partition in sorted(structure[system]):
            partition_inner = ""
            for test_name, partition_df in structure[system][partition]:

                table_data = get_last_n_runs(partition_df, 2)
                table_html = build_table(test_name, table_data.to_dict(orient="records"))

                fig = create_plot(data_frame=partition_df, test_name=f"{test_name} - {partition}")
                if fig is not None:
                    filename = f"{test_name}_{system}_{partition}.png"
                    upload_plot(confluence_obj, os.environ.get('CONFLUENCE_SPACE_ID'), filename, fig)
                    image_tag = f'<ac:image><ri:attachment ri:filename="{filename}" /></ac:image>'
                    partition_inner += image_tag + table_html
                else:
                    partition_inner += table_html

            system_inner += wrap_in_expand(partition, partition_inner)

        search_start = f'<ac:parameter ac:name="title">{system}</ac:parameter><ac:rich-text-body>'
        search_end = '</ac:rich-text-body>'
        if search_start in body:
            pattern = re.escape(search_start) + r'.*?' + re.escape(search_end)
            replacement = search_start + system_inner + search_end
            body = re.sub(pattern, replacement, body, count=1, flags=re.DOTALL)
        else:
            body += wrap_in_expand(system, system_inner)
    try:
        confluence_obj.update_page(page_id=os.environ.get('CONFLUENCE_SPACE_ID'), title=page["title"], body=body)
    except:
        pass