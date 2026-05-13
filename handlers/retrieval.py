import ast

import pandas as pd
import sqlparse
from flask import render_template, redirect, url_for, request
from sql_metadata import Parser

from retrieval import rank_sentences, rank_sentences_more
import handlers.state as state
from handlers.utils import load_json_data, save_json_data, retrieve_filenames


def _retrieval(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    logdata = pd.DataFrame(logdata)
    annotation['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation['gold_sql'] = sqlparse.format(annotation['gold-sql'], reindent=True, keyword_case='upper').strip()
    if 'sql_decomposition' in annotation.keys():
        return redirect(url_for("decomposition", annotation_id=annotation_id))
    most_relevant_examples_ = rank_sentences_more(
        annotation['sql_embedding'],
        [logdata['gold-sql'][i] for i in range(data_length) if not logdata['question'][i] == ""],
        [logdata['sql_embedding'][i] for i in range(data_length) if not logdata['question'][i] == ""],
        [logdata['gold-question'][i] for i in range(data_length) if not logdata['question'][i] == ""]
    )
    most_relevant_examples = [{'sql': x[0], 'question': x[1]} for x in most_relevant_examples_]
    schema = load_json_data(state.SCHEMA_FILE.format(DATABASE=state.DATABASE.lower()))
    schema = pd.DataFrame(schema)

    most_relevant_tables_ = rank_sentences(annotation['sql_embedding'], list(schema['schema']), list(schema["schema_embedding"]))
    most_relevant_tables = Parser(annotation['gold-sql']).tables
    len_tables = len(most_relevant_tables)
    try:
        most_relevant_tables = Parser(annotation['gold-sql']).tables
        len_tables = len(most_relevant_tables)
    except Exception as e:
        print(str(e))
        most_relevant_tables = []
        len_tables = min(5, len(most_relevant_tables_))
    for t in most_relevant_tables_:
        if t[0].split(',')[0] not in most_relevant_tables:
            most_relevant_tables.append(t[0].split(',')[0])

    annotation['suggested_examples'] = most_relevant_examples[:5]
    annotation['examples'] = most_relevant_examples[5:(min(10, len(most_relevant_examples) - 5))]
    annotation['tables'] = most_relevant_tables[len_tables:(min(10, len(most_relevant_tables) - len_tables))]
    annotation['suggested_tables'] = most_relevant_tables[:len_tables]
    return render_template("retrieval.html", annotation=annotation, annotation_id=annotation_id, data_length=data_length)


def _decomposed_retrieval(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    logdata = pd.DataFrame(logdata)
    annotation['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation['gold_sql'] = sqlparse.format(annotation['gold-sql'], reindent=True, keyword_case='upper').strip()
    annotations = annotation
    for i in range(len(annotations['sql_decomposition'])):
        most_relevant_examples_ = rank_sentences_more(
            annotations['sql_decomposition'][i]['sql_embedding'],
            [logdata['gold-sql'][j] for j in range(data_length) if not logdata['question'][j] == ""],
            [logdata['sql_embedding'][j] for j in range(data_length) if not logdata['question'][j] == ""],
            [logdata['gold-question'][j] for j in range(data_length) if not logdata['question'][j] == ""]
        )
        most_relevant_examples = [{'sql': x[0], 'question': x[1]} for x in most_relevant_examples_]
        schema = load_json_data(state.SCHEMA_FILE.format(DATABASE=state.DATABASE.lower()))
        schema = pd.DataFrame(schema)
        most_relevant_tables_ = rank_sentences(annotations['sql_decomposition'][i]['sql_embedding'], list(schema['schema']), list(schema["schema_embedding"]))
        try:
            most_relevant_tables = [t.upper() for t in Parser(annotations['sql_decomposition'][i]['gold-sql']).tables]
            len_tables = len(most_relevant_tables)
        except Exception as e:
            print(str(e))
            most_relevant_tables = []
            len_tables = min(5, len(most_relevant_tables_))
        for t in most_relevant_tables_:
            if t[0].split(',')[0] not in most_relevant_tables:
                most_relevant_tables.append(t[0].split(',')[0])
        annotations['sql_decomposition'][i]['gold_sql'] = sqlparse.format(annotations['sql_decomposition'][i]['gold-sql'], reindent=True, keyword_case='upper')
        annotations['sql_decomposition'][i]['suggested_examples'] = most_relevant_examples[:2]
        annotations['sql_decomposition'][i]['examples'] = most_relevant_examples[3:(min(5, len(most_relevant_examples) - 5))]
        annotations['sql_decomposition'][i]['tables'] = most_relevant_tables[len_tables:(min(len_tables + 2, len(most_relevant_tables) - len_tables))]
        tables = retrieve_filenames(state.SCHEMA_FOLDER.format(DATABASE=state.DATABASE.lower()))
        if annotation.get("db_id") == "dw":
            tables = [t[3:] for t in tables]
        annotations['sql_decomposition'][i]['suggested_tables'] = most_relevant_tables[:len_tables]
        annotations['sql_decomposition'][i]['suggested_tables'] = list(set(annotations['sql_decomposition'][i]['suggested_tables']) & set(tables))
    annotations['percentage'] = round(num_annotated / data_length * 100, 2)
    annotations['gold_sql'] = sqlparse.format(annotations['gold-sql'], reindent=True, keyword_case='upper')
    return render_template("decomposed_retrieval.html", annotations=annotations, annotation_id=annotation_id, data_length=data_length)


def save(annotation_id, type_, old_time):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    data_length = len(logdata)
    if len(state.REL_TABLES) < annotation_id or len(state.REL_EXAMPLES) < annotation_id:
        state.REL_TABLES = [''] * data_length
        state.REL_EXAMPLES = [''] * data_length
    state.REL_EXAMPLES[annotation_id] = {}
    state.REL_TABLES[annotation_id] = {}
    if type_ == 'decomposed_sql':
        annotation = logdata[annotation_id - 1]
        for decomposed in annotation['sql_decomposition']:
            selected_suggested_examples = request.form.getlist('selected_suggested_examples' + decomposed['title'])
            selected_examples = request.form.getlist('selected_examples' + decomposed['title'])
            state.REL_EXAMPLES[annotation_id][decomposed['title']] = [ast.literal_eval(item) for item in selected_suggested_examples] + [ast.literal_eval(item) for item in selected_examples]
            state.REL_TABLES[annotation_id][decomposed['title']] = request.form.getlist('selected_suggested_tables' + decomposed['title']) + request.form.getlist('selected_tables' + decomposed['title'])
        url = "decomposed_sql_annotation"
    else:
        selected_suggested_examples = request.form.getlist('selected_suggested_examples')
        selected_examples = request.form.getlist('selected_examples')
        selected_suggested_tables = request.form.getlist('selected_suggested_tables')
        selected_tables = request.form.getlist('selected_tables')

        state.REL_EXAMPLES[annotation_id] = [ast.literal_eval(item) for item in selected_suggested_examples] + [ast.literal_eval(item) for item in selected_examples]
        if state.DATABASE == "FIBEN":
            selected_suggested_tables = [x.split('.')[1] if '.' in x else x for x in selected_suggested_tables]
        state.REL_TABLES[annotation_id] = selected_suggested_tables + selected_tables
        url = "sql_annotation"
    logdata[annotation_id - 1]['time']['retrieval'] = state.SINGLE_TIME - old_time
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)
    return redirect(url_for(url, annotation_id=annotation_id))
