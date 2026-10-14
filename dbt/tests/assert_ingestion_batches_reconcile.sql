select batch_id
from {{ source('olist_audit', 'batch_reconciliation') }}
where
    upper(status) <> 'SUCCEEDED'
    or expected_files <> loaded_files
    or expected_rows <> loaded_rows
    or file_difference <> 0
    or row_difference <> 0
