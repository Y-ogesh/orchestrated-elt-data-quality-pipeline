#!/usr/bin/env python3
"""Generate the source-controlled Olist Power BI PBIP/TMDL project."""

import hashlib
import json
import re
import shutil
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "power_bi" / "OlistELTReporting"
MODEL_ROOT = PROJECT_ROOT / "OlistELTReporting.SemanticModel"
REPORT_ROOT = PROJECT_ROOT / "OlistELTReporting.Report"
DEFINITION_ROOT = MODEL_ROOT / "definition"
TABLE_ROOT = DEFINITION_ROOT / "tables"

SCHEMA_PBIP = (
    "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
)
SCHEMA_PBISM = (
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/"
    "definitionProperties/1.0.0/schema.json"
)
SCHEMA_PBIR = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definitionProperties/2.0.0/schema.json"
)
SCHEMA_REPORT = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "report/3.3.0/schema.json"
)
SCHEMA_VERSION = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "versionMetadata/1.0.0/schema.json"
)
SCHEMA_PAGES = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "pagesMetadata/1.1.0/schema.json"
)
SCHEMA_PAGE = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "page/2.1.0/schema.json"
)
SCHEMA_VISUAL = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "visualContainer/2.14.0/schema.json"
)


def columns(spec):
    return [tuple(item.split(":")) for item in spec.split()]


# Types: s=string, i=int64, d=decimal, x=double, b=boolean, date=dateTime, dt=dateTime.
TABLES = {
    "Report Orders": (
        "MARTS",
        "REPORT_FCT_ORDERS",
        columns(
            "ORDER_KEY:s ORDER_CUSTOMER_KEY:s CUSTOMER_KEY:s PURCHASE_DATE_KEY:i "
            "ORDER_ID:s ORDER_STATUS:s ORDER_PURCHASE_TIMESTAMP:dt "
            "ORDER_APPROVED_TIMESTAMP:dt ORDER_DELIVERED_CARRIER_TIMESTAMP:dt "
            "ORDER_DELIVERED_CUSTOMER_TIMESTAMP:dt "
            "ORDER_ESTIMATED_DELIVERY_TIMESTAMP:dt ORDER_ITEM_COUNT:i "
            "DISTINCT_PRODUCT_COUNT:i DISTINCT_SELLER_COUNT:i "
            "ITEM_MERCHANDISE_VALUE:d FREIGHT_VALUE:d ITEM_TOTAL_VALUE:d "
            "PAYMENT_COUNT:i DISTINCT_PAYMENT_TYPE_COUNT:i "
            "MAXIMUM_PAYMENT_INSTALLMENTS:i PAYMENT_TOTAL_VALUE:d "
            "PAYMENT_ITEM_DIFFERENCE:d IS_PAYMENT_RECONCILIATION_EXCEPTION:b "
            "IS_MISSING_ITEMS:b IS_MISSING_PAYMENTS:b DELIVERY_DAYS:i "
            "IS_LATE_DELIVERY:b SOURCE_LOADED_AT:dt"
        ),
        "ORDER_KEY",
    ),
    "Report Order Items": (
        "MARTS",
        "REPORT_FCT_ORDER_ITEMS",
        columns(
            "ORDER_ITEM_KEY:s ORDER_KEY:s PRODUCT_KEY:s SELLER_KEY:s "
            "SHIPPING_LIMIT_DATE_KEY:i ORDER_ID:s ORDER_ITEM_ID:i ITEM_PRICE:d "
            "FREIGHT_VALUE:d ITEM_TOTAL_VALUE:d SHIPPING_LIMIT_TIMESTAMP:dt "
            "SOURCE_LOADED_AT:dt"
        ),
        "ORDER_ITEM_KEY",
    ),
    "Report Order Payments": (
        "MARTS",
        "REPORT_FCT_ORDER_PAYMENTS",
        columns(
            "PAYMENT_KEY:s ORDER_KEY:s ORDER_ID:s PAYMENT_SEQUENTIAL:i PAYMENT_TYPE:s "
            "PAYMENT_INSTALLMENTS:i PAYMENT_VALUE:d SOURCE_LOADED_AT:dt"
        ),
        "PAYMENT_KEY",
    ),
    "Report Order Reviews": (
        "MARTS",
        "REPORT_FCT_ORDER_REVIEWS",
        columns(
            "REVIEW_KEY:s ORDER_KEY:s REVIEW_CREATION_DATE_KEY:i REVIEW_ID:s ORDER_ID:s "
            "REVIEW_SCORE:i REVIEW_COMMENT_TITLE:s REVIEW_COMMENT_MESSAGE:s "
            "REVIEW_CREATION_TIMESTAMP:dt REVIEW_ANSWER_TIMESTAMP:dt "
            "SOURCE_LOADED_AT:dt"
        ),
        "REVIEW_KEY",
    ),
    "Date": (
        "MARTS",
        "REPORT_DIM_DATE",
        columns(
            "DATE_KEY:i DATE_DAY:date DAY_OF_MONTH:i DAY_OF_WEEK_NUMBER:i "
            "DAY_OF_WEEK_NAME:s ISO_WEEK_NUMBER:i MONTH_NUMBER:i MONTH_NAME:s "
            "QUARTER_NUMBER:i YEAR_NUMBER:i IS_WEEKEND:b"
        ),
        "DATE_DAY",
    ),
    "Customers": (
        "MARTS",
        "REPORT_DIM_CUSTOMER",
        columns(
            "CUSTOMER_KEY:s CUSTOMER_UNIQUE_ID:s FIRST_ORDER_DATE:date "
            "LAST_ORDER_DATE:date LIFETIME_ORDER_COUNT:i"
        ),
        "CUSTOMER_KEY",
    ),
    "Order Customers": (
        "MARTS",
        "REPORT_DIM_ORDER_CUSTOMER",
        columns(
            "ORDER_CUSTOMER_KEY:s CUSTOMER_KEY:s GEOGRAPHY_KEY:s CUSTOMER_ID:s "
            "CUSTOMER_UNIQUE_ID:s CUSTOMER_ZIP_CODE_PREFIX:s CUSTOMER_CITY:s "
            "CUSTOMER_STATE:s"
        ),
        "ORDER_CUSTOMER_KEY",
    ),
    "Products": (
        "MARTS",
        "REPORT_DIM_PRODUCT",
        columns(
            "PRODUCT_KEY:s CATEGORY_KEY:s PRODUCT_ID:s PRODUCT_CATEGORY_NAME:s "
            "PRODUCT_NAME_LENGTH:i PRODUCT_DESCRIPTION_LENGTH:i "
            "PRODUCT_PHOTOS_QUANTITY:i PRODUCT_WEIGHT_GRAMS:d PRODUCT_LENGTH_CM:d "
            "PRODUCT_HEIGHT_CM:d PRODUCT_WIDTH_CM:d"
        ),
        "PRODUCT_KEY",
    ),
    "Categories": (
        "MARTS",
        "REPORT_DIM_CATEGORY",
        columns(
            "CATEGORY_KEY:s PRODUCT_CATEGORY_NAME:s "
            "PRODUCT_CATEGORY_NAME_ENGLISH:s TRANSLATION_STATUS:s"
        ),
        "CATEGORY_KEY",
    ),
    "Sellers": (
        "MARTS",
        "REPORT_DIM_SELLER",
        columns(
            "SELLER_KEY:s GEOGRAPHY_KEY:s SELLER_ID:s SELLER_ZIP_CODE_PREFIX:s "
            "SELLER_CITY:s SELLER_STATE:s"
        ),
        "SELLER_KEY",
    ),
    "Geography": (
        "MARTS",
        "REPORT_DIM_GEOGRAPHY",
        columns(
            "GEOGRAPHY_KEY:s POSTAL_CODE_PREFIX:s CITY:s STATE_CODE:s LATITUDE:x "
            "LONGITUDE:x OBSERVATION_COUNT:i EXACT_DUPLICATE_COUNT:i "
            "INVALID_COORDINATE_COUNT:i IS_UNKNOWN:b"
        ),
        "GEOGRAPHY_KEY",
    ),
    "Pipeline Runs": (
        "AUDIT",
        "PBI_PIPELINE_RUNS",
        columns(
            "RUN_ID:s FINAL_STATE:s STARTED_AT:dt ENDED_AT:dt "
            "OBSERVED_TASK_SPAN_SECONDS:i RETRY_ATTEMPT_COUNT:i "
            "ROOT_FAILED_ATTEMPT_COUNT:i WARNING_COUNT:i QUALITY_FAILURE_COUNT:i "
            "VERIFIED_SOURCE_ROWS:i ACCEPTED_ROWS:i REJECTED_ROWS:i "
            "PUBLISHED_VERSION:s PUBLISHED_AT:dt IS_PUBLISHED:b"
        ),
        "RUN_ID",
    ),
    "Pipeline Health": (
        "AUDIT",
        "PBI_PIPELINE_HEALTH",
        columns(
            "CURRENT_REPORTING_VERSION:s LATEST_VALIDATED_RUN_ID:s LATEST_VALIDATED_AT:dt "
            "LATEST_PIPELINE_STATUS:s QUALITY_TESTS_PASSED:i QUALITY_TEST_WARNINGS:i "
            "QUALITY_TEST_FAILURES:i FRESHNESS_SOURCES_PASSED_AT_VALIDATION:i "
            "SOURCE_ROWS:i ACCEPTED_ROWS:i REJECTED_OR_MISSING_ROWS:i "
            "TRACEABLE_REJECTED_ROWS:i REJECTION_DIAGNOSTICS:i "
            "UNLOCATED_REJECTION_DIAGNOSTICS:i MAXIMUM_FRESHNESS_AGE_HOURS:i "
            "CURRENT_FRESHNESS_PASS_COUNT:i CURRENT_FRESHNESS_WARNING_COUNT:i "
            "CURRENT_FRESHNESS_ERROR_COUNT:i CURRENT_FRESHNESS_STATUS:s"
        ),
        None,
    ),
    "Source Freshness": (
        "AUDIT",
        "PBI_SOURCE_FRESHNESS",
        columns("SOURCE_NAME:s LAST_LOADED_AT:dt FRESHNESS_AGE_HOURS:i FRESHNESS_STATUS:s"),
        "SOURCE_NAME",
    ),
}

RELATIONSHIPS = (
    ("Report Orders", "PURCHASE_DATE_KEY", "Date", "DATE_KEY", True, "many", "one"),
    ("Report Orders", "CUSTOMER_KEY", "Customers", "CUSTOMER_KEY", True, "many", "one"),
    (
        "Report Orders",
        "ORDER_CUSTOMER_KEY",
        "Order Customers",
        "ORDER_CUSTOMER_KEY",
        True,
        "many",
        "one",
    ),
    ("Report Order Items", "ORDER_KEY", "Report Orders", "ORDER_KEY", True, "many", "one"),
    (
        "Report Order Payments",
        "ORDER_KEY",
        "Report Orders",
        "ORDER_KEY",
        True,
        "many",
        "one",
    ),
    (
        "Report Order Reviews",
        "ORDER_KEY",
        "Report Orders",
        "ORDER_KEY",
        True,
        "many",
        "one",
    ),
    ("Report Order Items", "PRODUCT_KEY", "Products", "PRODUCT_KEY", True, "many", "one"),
    ("Products", "CATEGORY_KEY", "Categories", "CATEGORY_KEY", True, "many", "one"),
    ("Report Order Items", "SELLER_KEY", "Sellers", "SELLER_KEY", True, "many", "one"),
    (
        "Order Customers",
        "GEOGRAPHY_KEY",
        "Geography",
        "GEOGRAPHY_KEY",
        True,
        "many",
        "one",
    ),
    (
        "Report Order Items",
        "SHIPPING_LIMIT_DATE_KEY",
        "Date",
        "DATE_KEY",
        False,
        "many",
        "one",
    ),
    (
        "Report Order Reviews",
        "REVIEW_CREATION_DATE_KEY",
        "Date",
        "DATE_KEY",
        False,
        "many",
        "one",
    ),
)

CURRENCY_MEASURES = {
    "Total Payment Value",
    "Average Order Value",
    "Merchandise Value",
    "Freight Value",
    "Delivered GMV",
    "Delivered GMV per Delivered Order",
    "Item Merchandise Value",
    "Item Freight Value",
}
PERCENT_MEASURES = {
    "Delivery Success Rate",
    "On-Time Delivery Rate",
    "Late Delivery Rate",
    "Late Delivery Rate for Selected Items",
    "Pipeline Run Success Rate",
}
DECIMAL_MEASURES = {"Average Delivery Days": "0.0", "Average Review Score": "0.00"}
DATE_MEASURES = {"Latest Validated At"}
TEXT_MEASURES = {
    "Latest Pipeline Status",
    "Current Freshness Status",
    "Latest Validated Pipeline Run",
    "Current Published Version",
}

MONEY_COLUMNS = {
    "ITEM_MERCHANDISE_VALUE",
    "FREIGHT_VALUE",
    "ITEM_TOTAL_VALUE",
    "PAYMENT_TOTAL_VALUE",
    "PAYMENT_ITEM_DIFFERENCE",
    "ITEM_PRICE",
    "PAYMENT_VALUE",
}


def quote(name):
    return "'" + name.replace("'", "''") + "'"


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content.rstrip() + "\n")


def write_json(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False))


def parse_measures(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    folder = "Executive KPIs"
    measures = []
    current = None
    expression = []
    header = re.compile(r"^([A-Za-z][A-Za-z0-9 &()/\-]+) =$")

    def finish():
        if current is not None:
            measures.append((current, "\n".join(expression).strip(), active_folder))

    active_folder = folder
    for line in lines[6:]:
        if line.startswith("// Display folder: "):
            finish()
            current = None
            expression = []
            folder = line.split(": ", 1)[1]
            active_folder = folder
            continue
        # DAX variables can also end in `` =``; only top-level measure headers
        # should start a new measure block.
        match = None if line.startswith("VAR ") else header.match(line)
        if match:
            finish()
            current = match.group(1)
            expression = []
            active_folder = folder
        elif current is not None and not line.startswith("//"):
            expression.append(line)
    finish()
    if len(measures) != 41:
        raise ValueError(f"Expected 41 measures, found {len(measures)}")
    if any(not expression for _, expression, _ in measures):
        raise ValueError("Every measure must have a DAX expression")
    return measures


def measure_format(name):
    if name in CURRENCY_MEASURES:
        return "R$ #,0.00"
    if name in PERCENT_MEASURES:
        return "0.0%"
    if name in DECIMAL_MEASURES:
        return DECIMAL_MEASURES[name]
    if name in DATE_MEASURES:
        return "General Date"
    if name in TEXT_MEASURES:
        return "General"
    return "#,0"


def column_format(name, kind):
    if name in MONEY_COLUMNS:
        return "R$ #,0.00"
    if name in {"LATITUDE", "LONGITUDE"}:
        return "0.000000"
    if kind == "d":
        return "0.000"
    if kind == "i":
        return "#,0"
    if kind == "date":
        return "Short Date"
    if kind == "dt":
        return "General Date"
    return None


def table_tmdl(display_name, schema, source_name, source_columns, key):
    lines = [
        f"/// {display_name}: imported from {schema}.{source_name}.",
        f"table {quote(display_name)}",
    ]
    if display_name == "Date":
        lines.append("\tdataCategory: Time")
    lines.append("")
    type_map = {
        "s": "string",
        "i": "int64",
        "d": "decimal",
        "x": "double",
        "b": "boolean",
        "date": "dateTime",
        "dt": "dateTime",
    }
    for name, kind in source_columns:
        lines.extend([f"\tcolumn {quote(name)}", f"\t\tdataType: {type_map[kind]}"])
        if name == key:
            lines.append("\t\tisKey")
        if name.endswith("_KEY") or name == "SOURCE_LOADED_AT":
            lines.append("\t\tisHidden")
        formatted = column_format(name, kind)
        if formatted:
            lines.append(f"\t\tformatString: {formatted}")
        lines.extend(["\t\tsummarizeBy: none", f"\t\tsourceColumn: {name}"])
        if display_name == "Date" and name == "MONTH_NAME":
            lines.append("\t\tsortByColumn: MONTH_NUMBER")
        if display_name == "Date" and name == "DAY_OF_WEEK_NAME":
            lines.append("\t\tsortByColumn: DAY_OF_WEEK_NUMBER")
        lines.append("")
    if display_name == "Date":
        lines.extend(
            [
                "\tcolumn 'Year Month' = FORMAT ( 'Date'[DATE_DAY], \"yyyy-MM\" )",
                "\t\tdataType: string",
                "\t\tsummarizeBy: none",
                "\t\tsortByColumn: 'Year Month Sort'",
                "",
                "\tcolumn 'Year Month Sort' = YEAR ( 'Date'[DATE_DAY] ) * 100 + "
                "MONTH ( 'Date'[DATE_DAY] )",
                "\t\tdataType: int64",
                "\t\tisHidden",
                "\t\tformatString: 0",
                "\t\tsummarizeBy: none",
                "",
            ]
        )
    lines.extend(
        [
            f"\tpartition {quote(display_name)} = m",
            "\t\tmode: import",
            "\t\tsource =",
            "\t\t\t\tlet",
            "\t\t\t\t    Source = Snowflake.Databases(SnowflakeServer, "
            'SnowflakeWarehouse, [Role=SnowflakeRole, Implementation="2.0", '
            "CreateNavigationProperties=false]),",
            '\t\t\t\t    Database = Source{[Name=SnowflakeDatabase, Kind="Database"]}[Data],',
            f'\t\t\t\t    Schema = Database{{[Name="{schema}", Kind="Schema"]}}[Data],',
            f'\t\t\t\t    ReportingView = Schema{{[Name="{source_name}", Kind="View"]}}[Data]',
            "\t\t\t\tin",
            "\t\t\t\t    ReportingView",
            "",
            "\tannotation PBI_ResultType = Table",
        ]
    )
    return "\n".join(lines)


def measures_tmdl(measures):
    lines = [
        "/// Dedicated measure home table; the placeholder column is hidden.",
        "table _Measures",
        "",
    ]
    for name, expression, folder in measures:
        lines.extend([f"\tmeasure {quote(name)} = ```"])
        lines.extend(f"\t\t\t{line}" if line else "" for line in expression.splitlines())
        lines.extend(
            [
                "\t\t\t```",
                f"\t\tformatString: {measure_format(name)}",
                f"\t\tdisplayFolder: {json.dumps(folder)}",
                "",
            ]
        )
    lines.extend(
        [
            "\tcolumn _Placeholder",
            "\t\tdataType: string",
            "\t\tisHidden",
            "\t\tsummarizeBy: none",
            "\t\tsourceColumn: [Value]",
            "",
            "\tpartition _Measures = calculated",
            "\t\tmode: import",
            '\t\tsource = ROW("Value", "Measures")',
        ]
    )
    return "\n".join(lines)


def relationship_tmdl():
    lines = []
    for from_table, from_column, to_table, to_column, active, from_card, to_card in RELATIONSHIPS:
        identity = f"{from_table}.{from_column}->{to_table}.{to_column}"
        relation_id = uuid5(NAMESPACE_URL, "olist-power-bi:" + identity)
        lines.append(f"relationship {relation_id}")
        if not active:
            lines.append("\tisActive: false")
        if from_card != "many":
            lines.append(f"\tfromCardinality: {from_card}")
        if to_card != "one":
            lines.append(f"\ttoCardinality: {to_card}")
        lines.extend(
            [
                "\tcrossFilteringBehavior: oneDirection",
                f"\tfromColumn: {quote(from_table)}.{quote(from_column)}",
                f"\ttoColumn: {quote(to_table)}.{quote(to_column)}",
                "",
            ]
        )
    return "\n".join(lines)


def page_id(name):
    return hashlib.sha1(("olist-power-bi:" + name).encode()).hexdigest()[:20]


def visual_id(page_name, label):
    return hashlib.sha1(f"olist-power-bi:{page_name}:{label}".encode()).hexdigest()[:20]


def column_field(table, column):
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def measure_field(measure):
    return {
        "Measure": {
            "Expression": {"SourceRef": {"Entity": "_Measures"}},
            "Property": measure,
        }
    }


def projection(field, query_ref, native_ref, active=False):
    result = {"field": field, "queryRef": query_ref, "nativeQueryRef": native_ref}
    if active:
        result["active"] = True
    return result


def visual_position(x, y, width, height, z):
    return {
        "x": x,
        "y": y,
        "z": z,
        "height": height,
        "width": width,
        "tabOrder": z,
    }


def visual_filter(name, field, kind="Advanced"):
    return {
        "name": hashlib.sha1(("olist-power-bi:filter:" + name).encode()).hexdigest()[:20],
        "field": field,
        "type": kind,
    }


def card_visual(
    page,
    measure,
    x,
    y,
    width,
    height,
    z,
    label_font_size=None,
    display_label=None,
):
    field = measure_field(measure)
    query_ref = f"_Measures.{measure}"
    native_ref = display_label or measure
    visual = {
        "visualType": "cardVisual",
        "query": {
            "queryState": {
                "Data": {"projections": [projection(field, query_ref, native_ref)]}
            },
            "sortDefinition": {
                "sort": [{"field": field, "direction": "Descending"}],
                "isDefaultSort": True,
            },
        },
    }
    label_properties = {
        "displayUnits": {"expr": {"Literal": {"Value": "0D"}}},
    }
    if label_font_size is not None:
        label_properties["fontSize"] = {
            "expr": {"Literal": {"Value": f"{label_font_size}D"}}
        }
    visual["objects"] = {
        "label": [{"properties": label_properties, "selector": {"id": "default"}}]
    }
    return {
        "$schema": SCHEMA_VISUAL,
        "name": visual_id(page, f"card:{measure}"),
        "position": visual_position(x, y, width, height, z),
        "visual": visual,
        "filterConfig": {"filters": [visual_filter(f"{page}:{measure}", field)]},
    }


def chart_visual(
    page,
    label,
    category,
    measure,
    x,
    y,
    width,
    height,
    z,
    visual_type="lineChart",
    category_label=None,
):
    table, column = category
    category_value = column_field(table, column)
    measure_value = measure_field(measure)
    sort_field = category_value if visual_type == "lineChart" else measure_value
    sort_direction = "Ascending" if visual_type == "lineChart" else "Descending"
    return {
        "$schema": SCHEMA_VISUAL,
        "name": visual_id(page, f"chart:{label}"),
        "position": visual_position(x, y, width, height, z),
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
                            projection(
                                category_value,
                                f"{table}.{column}",
                                category_label or column,
                                active=True,
                            )
                        ]
                    },
                    "Y": {
                        "projections": [projection(measure_value, f"_Measures.{measure}", measure)]
                    },
                },
                "sortDefinition": {
                    "sort": [{"field": sort_field, "direction": sort_direction}],
                    "isDefaultSort": True,
                },
            },
        },
        "filterConfig": {
            "filters": [
                visual_filter(f"{page}:{label}:category", category_value, "Categorical"),
                visual_filter(f"{page}:{label}:measure", measure_value),
            ]
        },
    }


def table_visual(page, label, fields, x, y, width, height, z):
    projections = []
    filters = []
    for table, name, kind in fields:
        if kind == "measure":
            field = measure_field(name)
            query_ref = f"_Measures.{name}"
        else:
            field = column_field(table, name)
            query_ref = f"{table}.{name}"
        projections.append(projection(field, query_ref, name))
        filters.append(visual_filter(f"{page}:{label}:{query_ref}", field))
    return {
        "$schema": SCHEMA_VISUAL,
        "name": visual_id(page, f"table:{label}"),
        "position": visual_position(x, y, width, height, z),
        "visual": {
            "visualType": "tableEx",
            "query": {"queryState": {"Values": {"projections": projections}}},
        },
        "filterConfig": {"filters": filters},
    }


def slicer_visual(page, label, table, column, x, y, width, height, z, display_label=None):
    field = column_field(table, column)
    return {
        "$schema": SCHEMA_VISUAL,
        "name": visual_id(page, f"slicer:{label}"),
        "position": visual_position(x, y, width, height, z),
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            projection(
                                field,
                                f"{table}.{column}",
                                display_label or column,
                                active=True,
                            )
                        ]
                    }
                }
            },
            "objects": {
                "data": [
                    {
                        "properties": {
                            "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}
                        }
                    }
                ]
            },
        },
        "filterConfig": {"filters": [visual_filter(f"{page}:{label}", field, "Categorical")]},
    }


def report_visuals():
    executive = "Executive Overview"
    operations = "Operations & Data Quality"

    page_one = []
    for index, measure in enumerate(
        ("Total Orders", "Total Payment Value", "Average Order Value", "Customer Count")
    ):
        page_one.append(card_visual(executive, measure, 15 + 305 * index, 10, 290, 90, index))
    page_one.extend(
        [
            slicer_visual(
                executive, "Month", "Date", "Year Month", 15, 110, 395, 70, 4, "Year Month"
            ),
            slicer_visual(
                executive,
                "Status",
                "Report Orders",
                "ORDER_STATUS",
                425,
                110,
                395,
                70,
                5,
                "Order Status",
            ),
            slicer_visual(
                executive,
                "Category",
                "Categories",
                "PRODUCT_CATEGORY_NAME_ENGLISH",
                835,
                110,
                400,
                70,
                6,
                "Product Category",
            ),
            chart_visual(
                executive,
                "Monthly Orders",
                ("Date", "Year Month"),
                "Total Orders",
                15,
                190,
                600,
                240,
                7,
                category_label="Year Month",
            ),
            chart_visual(
                executive,
                "Monthly Payment Value",
                ("Date", "Year Month"),
                "Total Payment Value",
                635,
                190,
                600,
                240,
                8,
                category_label="Year Month",
            ),
            chart_visual(
                executive,
                "Order Status",
                ("Report Orders", "ORDER_STATUS"),
                "Total Orders",
                15,
                445,
                350,
                255,
                9,
                "barChart",
                "Order Status",
            ),
            chart_visual(
                executive,
                "Category Performance",
                ("Categories", "PRODUCT_CATEGORY_NAME_ENGLISH"),
                "Item Merchandise Value",
                380,
                445,
                425,
                255,
                10,
                "barChart",
                "Product Category",
            ),
            table_visual(
                executive,
                "Customer Performance",
                [
                    ("Order Customers", "CUSTOMER_STATE", "column"),
                    ("_Measures", "Total Orders", "measure"),
                    ("_Measures", "Customer Count", "measure"),
                    ("_Measures", "Total Payment Value", "measure"),
                ],
                820,
                445,
                415,
                255,
                11,
            ),
        ]
    )

    page_two = []
    operation_measures = (
        "Delivered Orders",
        "Delivery Success Rate",
        "Late Deliveries",
        "On-Time Delivery Rate",
        "Average Delivery Days",
        "Latest Pipeline Status",
        "Latest Validated Pipeline Run",
        "Current Published Version",
        "Accepted Rows",
        "Rejected Rows",
        "Quality Tests Passed",
        "Quality Test Warnings",
        "Quality Test Failures",
        "Data Freshness Age Hours",
        "Current Freshness Status",
    )
    for index, measure in enumerate(operation_measures[:5]):
        page_two.append(
            card_visual(
                operations, measure, 15 + index * 245, 10, 230, 72, index, label_font_size=11
            )
        )
    pipeline_cards = (
        ("Latest Pipeline Status", 15, 92, 230),
        ("Latest Validated Pipeline Run", 260, 92, 475),
        ("Current Published Version", 750, 92, 485),
    )
    for offset, (measure, x, y, width) in enumerate(pipeline_cards, start=5):
        page_two.append(
            card_visual(
                operations,
                measure,
                x,
                y,
                width,
                82,
                offset,
                label_font_size=10,
            )
        )
    for offset, measure in enumerate(operation_measures[8:], start=8):
        display_label = {
            "Data Freshness Age Hours": "Freshness Age (Hours)",
        }.get(measure)
        page_two.append(
            card_visual(
                operations,
                measure,
                15 + (offset - 8) * 175,
                184,
                165,
                72,
                offset,
                label_font_size=9,
                display_label=display_label,
            )
        )
    page_two.extend(
        [
            slicer_visual(
                operations, "Month", "Date", "Year Month", 15, 270, 395, 70, 15, "Year Month"
            ),
            slicer_visual(
                operations,
                "Status",
                "Report Orders",
                "ORDER_STATUS",
                425,
                270,
                395,
                70,
                16,
                "Order Status",
            ),
            slicer_visual(
                operations,
                "Category",
                "Categories",
                "PRODUCT_CATEGORY_NAME_ENGLISH",
                835,
                270,
                400,
                70,
                17,
                "Product Category",
            ),
            table_visual(
                operations,
                "Seller Operations",
                [
                    ("Sellers", "SELLER_STATE", "column"),
                    ("_Measures", "Item Orders", "measure"),
                    ("_Measures", "Item Merchandise Value", "measure"),
                    ("_Measures", "Late Delivery Rate for Selected Items", "measure"),
                ],
                15,
                350,
                300,
                350,
                18,
            ),
            table_visual(
                operations,
                "Source Freshness",
                [
                    ("Source Freshness", "SOURCE_NAME", "column"),
                    ("Source Freshness", "LAST_LOADED_AT", "column"),
                    ("Source Freshness", "FRESHNESS_AGE_HOURS", "column"),
                    ("Source Freshness", "FRESHNESS_STATUS", "column"),
                ],
                330,
                350,
                380,
                350,
                19,
            ),
            chart_visual(
                operations,
                "Category Late Deliveries",
                ("Categories", "PRODUCT_CATEGORY_NAME_ENGLISH"),
                "Late Deliveries for Selected Items",
                725,
                350,
                510,
                350,
                20,
                "barChart",
                "Product Category",
            ),
        ]
    )
    return {executive: page_one, operations: page_two}


def build():
    measures = parse_measures(ROOT / "power_bi" / "measures.dax")
    write_json(
        PROJECT_ROOT / "OlistELTReporting.pbip",
        {
            "$schema": SCHEMA_PBIP,
            "version": "1.0",
            "artifacts": [{"report": {"path": "OlistELTReporting.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write_json(
        MODEL_ROOT / "definition.pbism",
        {"$schema": SCHEMA_PBISM, "version": "4.2", "settings": {"qnaEnabled": False}},
    )
    write(
        DEFINITION_ROOT / "database.tmdl",
        "database OlistELTReporting\n\tcompatibilityLevel: 1600\n\tcompatibilityMode: powerBI",
    )
    refs = "\n".join(f"ref table {quote(name)}" for name in (*TABLES, "_Measures"))
    write(
        DEFINITION_ROOT / "model.tmdl",
        """model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tdiscourageImplicitMeasures
\tsourceQueryCulture: en-US
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

"""
        + refs,
    )
    write(
        DEFINITION_ROOT / "expressions.tmdl",
        "\n\n".join(
            f'expression {name} = "{value}" meta '
            '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'
            for name, value in (
                ("SnowflakeServer", "SET_IN_POWER_BI_DESKTOP"),
                ("SnowflakeWarehouse", "OLIST_ELT_WH"),
                ("SnowflakeDatabase", "OLIST_ELT"),
                ("SnowflakeRole", "OLIST_ELT_ROLE"),
            )
        ),
    )
    for display_name, (schema, source_name, source_columns, key) in TABLES.items():
        write(
            TABLE_ROOT / f"{display_name}.tmdl",
            table_tmdl(display_name, schema, source_name, source_columns, key),
        )
    legacy_measure_path = TABLE_ROOT / "Measures.tmdl"
    if legacy_measure_path.exists():
        legacy_measure_path.unlink()
    write(TABLE_ROOT / "_Measures.tmdl", measures_tmdl(measures))
    write(DEFINITION_ROOT / "relationships.tmdl", relationship_tmdl())

    write_json(
        REPORT_ROOT / "definition.pbir",
        {
            "$schema": SCHEMA_PBIR,
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../OlistELTReporting.SemanticModel"}},
        },
    )
    write_json(
        REPORT_ROOT / "definition" / "version.json",
        {"$schema": SCHEMA_VERSION, "version": "2.0.0"},
    )
    write_json(
        REPORT_ROOT / "definition" / "report.json",
        {"$schema": SCHEMA_REPORT, "themeCollection": {}},
    )
    page_names = ("Executive Overview", "Operations & Data Quality")
    page_ids = [page_id(name) for name in page_names]
    write_json(
        REPORT_ROOT / "definition" / "pages" / "pages.json",
        {"$schema": SCHEMA_PAGES, "pageOrder": page_ids, "activePageName": page_ids[0]},
    )
    visuals_by_page = report_visuals()
    for name, identifier in zip(page_names, page_ids):
        page_root = REPORT_ROOT / "definition" / "pages" / identifier
        write_json(
            page_root / "page.json",
            {
                "$schema": SCHEMA_PAGE,
                "name": identifier,
                "displayName": name,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )
        visuals_root = page_root / "visuals"
        if visuals_root.exists():
            shutil.rmtree(visuals_root)
        for visual in visuals_by_page[name]:
            write_json(visuals_root / visual["name"] / "visual.json", visual)
    print(
        json.dumps(
            {
                "project": str(PROJECT_ROOT.relative_to(ROOT)),
                "import_tables": len(TABLES),
                "measure_home_tables": 1,
                "measures": len(measures),
                "relationships": len(RELATIONSHIPS),
                "report_pages": len(page_names),
                "visuals": sum(len(items) for items in visuals_by_page.values()),
            }
        )
    )


if __name__ == "__main__":
    build()
