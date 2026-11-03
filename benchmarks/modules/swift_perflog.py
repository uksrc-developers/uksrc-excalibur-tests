import os, logging

from perf_logs import DatabaseConnection
from reframe.core.logging import register_log_handler

# swiftdb data sending updates a sql database object on an OpenStack swift object store.
class SwiftDBHandler(logging.Handler):
    def __init__(self, container, db_file, os_options):
        super().__init__()
        self.container = container
        self.db_file = db_file
        self.os_options = os_options
        self.table_name = None
        self.pending_records = []

    def emit(self, record):
        self.table_name = getattr(record, '__rfm_check__', None).bench_name
        # Just collect records - don't hit the database yet
        content = getattr(record, '__rfm_check__', None).output_dict_list
        for output in content:
            self.pending_records.append({
                **output
            })

    def flush(self):
        if not self.pending_records:
            return

        with DatabaseConnection(
                container=self.container,
                db_file=self.db_file,
                os_options=self.os_options
        ) as db_c:
            # Create table if needed
            table_creation_string = f"CREATE TABLE IF NOT EXISTS {self.table_name} (testID INTEGER PRIMARY KEY AUTOINCREMENT"
            for k, v in self.pending_records[0].items():
                table_creation_string += f", {k} {('TEXT' if type(v)==str else 'REAL')} NOT NULL"
            table_creation_string+=");"
            db_c.cur.execute(table_creation_string)
            db_c.con.commit()
            execute_many_string = f"""INSERT INTO {self.table_name} ({", ".join(self.pending_records[0].keys())}) VALUES (:{", :".join(self.pending_records[0].keys())})"""
            # Insert all pending records
            db_c.cur.executemany(execute_many_string, self.pending_records)
            db_c.con.commit()
        self.pending_records = []

    def close(self):
        self.flush()
        super().close()

@register_log_handler("swiftdb")
def _create_handler(site_config, config_prefix):
    return SwiftDBHandler(
        container=os.environ.get('DB_CONTAINER', 'excalibur_tests_results'),
        db_file=os.environ.get('DB_FILE', 'reframe_results.db'),
        os_options={
            "interface": os.environ.get("OS_INTERFACE"),
            "region_name": os.environ.get('OS_REGION_NAME'),
        }
    )

site_configuration = {
    'logging': [
        {
            'handlers_perflog': [
                {
                    'type': 'swiftdb',
                    'level': 'info',
                    'debug': False,
                    'extras': {'facility': 'reframe'},
                    'ignore_keys': [],
                }
            ]
        }
    ]
}