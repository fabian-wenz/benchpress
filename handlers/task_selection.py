import time

from flask import render_template, redirect, url_for, request

import handlers.state as state


def _task_selection():
    annotation = {
        'tasks': state.DATA["tasks"],
        'models': state.DATA["models"],
        'task': state.TASK,
        'model': state.MODEL,
    }
    print(annotation)
    return render_template("task_selection.html", annotation=annotation)


def save():
    state.TASK = request.form.get('selected_task')
    state.MODEL = request.form.get('selected_model')
    state.OVERALL_TIME = time.time()
    state.SINGLE_TIME = time.time()
    return redirect(url_for("retrieval", annotation_id=1))
