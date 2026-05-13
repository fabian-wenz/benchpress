from flask import render_template, redirect, url_for, request

from generate import generate_improved_prompt
import handlers.state as state
from handlers.utils import load_json_data, save_json_data


def _feedback(annotation_id):
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    data_length = len(logdata)
    annotation = logdata[annotation_id - 1]
    annotation['prompt'] = state.PROMPT_TXT
    annotation['prompt_html'] = state.PROMPT_TXT[1:].replace('\n', '<br>\n')
    annotation['new_prompt'] = generate_improved_prompt(
        state.MODEL, state.API_KEY, state.PROMPT_TXT,
        logdata[annotation_id - 1]['options'],
        logdata[annotation_id - 1]['question'],
        logdata[annotation_id - 1]['comment'],
        state.DATABASE
    )
    annotation["options"] = "\n".join(f"• {opt}" for opt in logdata[annotation_id - 1]['options'])
    return render_template('feedback.html', annotation=annotation, annotation_id=annotation_id, data_length=data_length)


def save(annotation_id, old_time):
    selected_option = request.form.get('selected_option')
    if selected_option != "1":
        adjustment_text = request.form.get('adjustment_text')
        state.PROMPT_TXT = adjustment_text
    logdata = load_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()))
    logdata[annotation_id - 1]['time']['feedback'] = state.SINGLE_TIME - old_time
    save_json_data(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()), logdata)
    return redirect(url_for("retrieval", annotation_id=annotation_id + 1))
