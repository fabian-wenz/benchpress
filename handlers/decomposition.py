import sqlite3

import pandas as pd
import sqlparse
from flask import render_template, redirect, url_for, request

from generate import generate_combined_candidate
from retrieval import rank_sentences_more
import handlers.state as state
from handlers.utils import load_json_data, save_json_data


def _recompose_sql_annotation(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))

    annotation = logdata[annotation_id - 1]
    data_length = len(logdata)
    num_annotated = sum(1 for item in logdata if item['question'] != "")
    annotation['percentage'] = round(num_annotated / data_length * 100, 2)
    annotation['column'] = ['c']
    annotation['gold_sql'] = sqlparse.format(annotation['gold-sql'], reindent=True, keyword_case='upper').strip()
    logdata_ = pd.DataFrame(logdata)
    most_relevant_examples_ = rank_sentences_more(
        annotation['sql_embedding'],
        [logdata_['gold-sql'][i] for i in range(data_length) if not logdata_['question'][i] == ""],
        [logdata_['sql_embedding'][i] for i in range(data_length) if not logdata_['question'][i] == ""],
        [logdata_['gold-question'][i] for i in range(data_length) if not logdata['question'][i] == ""]
    )
    most_relevant_examples = [{'sql': x[0], 'question': x[1]} for x in most_relevant_examples_]
    nl_annotations = {}
    for i in range(len(annotation['sql_decomposition'])):
        nl_annotations[annotation['sql_decomposition'][i]['title']] = annotation['sql_decomposition'][i]['question']
    annotation_ = annotation

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

    annotation['options'] = generate_combined_candidate(
        state.MODEL, state.API_KEY,
        annotation['sql_in_cte'], nl_annotations,
        most_relevant_examples[1]["question"],
        state.PROMPT_TXT,
        annotation_['rows'], annotation_['column_names']
    )
    return render_template("recompose_sql_annotation.html", annotation=annotation, annotation_id=annotation_id, data_length=data_length)


def save_retrieval(annotation_id, old_time):
    sql_in_cte = request.form.getlist('sql_in_cte')
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    logdata[annotation_id - 1]['sql_in_cte'] = sql_in_cte[0]
    logdata[annotation_id - 1]['time']['decomposition'] = state.SINGLE_TIME - old_time
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)
    return redirect(url_for("decomposed_retrieval", annotation_id=annotation_id))
