import sqlite3

import sqlparse
from flask import render_template, redirect, url_for, request

from generate import generate_candidate
import handlers.state as state
from handlers.utils import load_json_data, save_json_data


def _decomposition(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    annotation['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation['gold_sql'] = sqlparse.format(annotation['gold-sql'], reindent=True, keyword_case='upper').strip()
    return render_template("decomposition.html", annotation=annotation, annotation_id=annotation_id, data_length=data_length)


def _sql_annotation(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    annotation_ = annotation
    annotation_['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation_['gold_sql'] = sqlparse.format(annotation_['gold-sql'], reindent=True, keyword_case='upper')

    conn = sqlite3.connect("./data/" + state.DATABASE.lower() + "/database/" + annotation_['db_id'] + "/" + annotation_['db_id'] + ".sqlite")
    cursor = conn.cursor()

    try:
        cursor.execute(annotation_['gold-sql'].replace("FIBEN.", ""))
        annotation_['rows'] = cursor.fetchall()
        annotation_['rows'] = annotation_['rows'][:min(10, len(annotation['rows']))]
        annotation_['column_names'] = [desc[0] for desc in cursor.description]
        conn.close()
    except Exception as e:
        print(e)
        annotation_['rows'] = [[str(e)]]
        annotation_['column_names'] = ["ERROR"]

    annotation['options'] = generate_candidate(
        state.MODEL, state.API_KEY, state.PROMPT, state.PROMPT_TXT,
        annotation['gold-sql'],
        state.REL_TABLES[annotation_id], state.REL_EXAMPLES[annotation_id],
        annotation['db_id'], state.DATABASE,
        annotation_['rows'], annotation_['column_names']
    )
    logdata[annotation_id - 1] = annotation
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)
    if "comment" not in annotation.keys():
        annotation['comment'] = ""
    return render_template('sql_annotation.html', annotation=annotation, annotation_id=annotation_id, data_length=data_length)


def _decomposed_sql_annotation(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    annotation['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation['gold_sql'] = sqlparse.format(annotation['gold-sql'], reindent=True, keyword_case='upper').strip()
    annotations = annotation

    conn = sqlite3.connect("./data/" + state.DATABASE.lower() + "/database/" + annotation['db_id'] + "/" + annotation['db_id'] + ".sqlite")
    cursor = conn.cursor()

    try:
        cursor.execute(annotation['gold-sql'].replace("FIBEN.", ""))
        annotations['rows'] = cursor.fetchall()
        annotations['rows'] = annotation['rows'][:min(10, len(annotation['rows']))]
        annotations['column_names'] = [desc[0] for desc in cursor.description]
        conn.close()
    except Exception as e:
        print(e)
        annotations['rows'] = [[str(e)]]
        annotations['column_names'] = ["ERROR"]

    for i in range(len(annotations['sql_decomposition'])):
        annotations['sql_decomposition'][i]['gold_sql'] = sqlparse.format(annotations['sql_decomposition'][i]['gold-sql'], reindent=True, keyword_case='upper').strip()
        annotations['sql_decomposition'][i]['options'] = generate_candidate(
            state.MODEL, state.API_KEY, state.PROMPT, state.PROMPT_TXT,
            annotations['sql_decomposition'][i]['gold-sql'],
            state.REL_TABLES[annotation_id][annotations['sql_decomposition'][i]['title']],
            state.REL_EXAMPLES[annotation_id][annotations['sql_decomposition'][i]['title']],
            annotation['db_id'], state.DATABASE,
            annotations['rows'], annotations['column_names']
        )
    logdata[annotation_id - 1] = annotations
    if "comment" not in annotation.keys():
        annotations['comment'] = ""
    return render_template('decomposed_sql_annotation.html', annotations=annotations, annotation_id=annotation_id, data_length=data_length)


def save(annotation_id, old_time):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    selected_option = request.form.get('selected_option')
    if selected_option == "adjustment":
        adjustment_text = request.form.get('adjustment_text')
        logdata[annotation_id - 1]["question"] = adjustment_text
        logdata[annotation_id - 1]['adjusted'] = True
    elif selected_option:
        logdata[annotation_id - 1]["question"] = selected_option
        logdata[annotation_id - 1]['adjusted'] = False
    comment = request.form.get('comment_text')
    logdata[annotation_id - 1]['comment'] = comment if comment else ""
    logdata[annotation_id - 1]['time']['annotation'] = state.SINGLE_TIME - old_time
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)

    if logdata[annotation_id - 1]['adjusted']:
        return redirect(url_for("feedback", annotation_id=annotation_id))
    return redirect(url_for("retrieval", annotation_id=annotation_id + 1))


def save_decomposed(annotation_id, old_time):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    annotation = logdata[annotation_id - 1]
    for i in range(len(annotation['sql_decomposition'])):
        selected_option = request.form.get('selected_option' + annotation['sql_decomposition'][i]['title'])
        if selected_option == "adjustment":
            adjustment_text = request.form.get('adjustment_text' + annotation['sql_decomposition'][i]['title'])
            logdata[annotation_id - 1]['sql_decomposition'][i]["question"] = adjustment_text
            logdata[annotation_id - 1]['sql_decomposition'][i]['adjusted'] = True
        elif selected_option:
            logdata[annotation_id - 1]['sql_decomposition'][i]["question"] = selected_option
            logdata[annotation_id - 1]['sql_decomposition'][i]['adjusted'] = False
        comment = request.form.get('comment_text' + annotation['sql_decomposition'][i]['title'])
        logdata[annotation_id - 1]['sql_decomposition'][i]['comment'] = comment if comment else ""
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)
    return redirect(url_for("recompose_sql_annotation", annotation_id=annotation_id))
