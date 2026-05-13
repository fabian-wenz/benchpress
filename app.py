import time

from flask import Flask, request, redirect, url_for

import handlers.state as state
from handlers.index import _index, _submit, _save_api_key_and_user_id
from handlers.upload import _upload_page
from handlers.task_selection import _task_selection
from handlers.retrieval import _retrieval, _decomposed_retrieval
from handlers.annotation import _decomposition, _sql_annotation, _decomposed_sql_annotation
from handlers.decomposition import _recompose_sql_annotation
from handlers.feedback import _feedback
from handlers.review import _review
import handlers.upload as upload_handler
import handlers.task_selection as task_selection_handler
import handlers.retrieval as retrieval_handler
import handlers.annotation as annotation_handler
import handlers.decomposition as decomposition_handler
import handlers.feedback as feedback_handler

app = Flask(__name__)


@app.route('/')
def index():
    return _index()


@app.route("/submit", methods=["POST"])
def submit():
    return _submit()


@app.route("/save_api_key_and_user_id", methods=["POST"])
def save_api_key_and_user_id():
    return _save_api_key_and_user_id()


@app.route("/upload")
def upload():
    return _upload_page()


@app.route("/task_selection")
def task_selection():
    return _task_selection()


@app.route('/retrieval/<int:annotation_id>')
def retrieval(annotation_id):
    return _retrieval(annotation_id)


@app.route('/decomposed_retrieval/<int:annotation_id>')
def decomposed_retrieval(annotation_id):
    return _decomposed_retrieval(annotation_id)


@app.route('/decomposition/<int:annotation_id>')
def decomposition(annotation_id):
    return _decomposition(annotation_id)


@app.route('/sql_annotation/<int:annotation_id>')
def sql_annotation(annotation_id):
    return _sql_annotation(annotation_id)


@app.route('/decomposed_sql_annotation/<int:annotation_id>')
def decomposed_sql_annotation(annotation_id):
    return _decomposed_sql_annotation(annotation_id)


@app.route('/recompose_sql_annotation/<int:annotation_id>')
def recompose_sql_annotation(annotation_id):
    return _recompose_sql_annotation(annotation_id)


@app.route('/feedback/<int:annotation_id>')
def feedback(annotation_id):
    return _feedback(annotation_id)


@app.route('/review')
def review():
    return _review()


@app.route('/save_and_next/', methods=['POST'])
def save_and_next():
    type_ = request.args.get('type')
    if type_ == 'upload':
        return upload_handler.save()
    if type_ == 'task_selection':
        return task_selection_handler.save()
    return redirect(url_for('index'))


@app.route('/save_and_next_annotation/<int:annotation_id>', methods=['POST'])
def save_and_next_annotation(annotation_id):
    type_ = request.args.get('type')
    old_time = state.SINGLE_TIME
    state.SINGLE_TIME = time.time()
    if type_ in ('retrieval', 'decomposed_sql'):
        return retrieval_handler.save(annotation_id, type_, old_time)
    if type_ == 'decomposed_retrieval':
        return decomposition_handler.save_retrieval(annotation_id, old_time)
    if type_ == 'decomposed_sql_annotation':
        return annotation_handler.save_decomposed(annotation_id, old_time)
    if type_ == 'sql_annotation':
        return annotation_handler.save(annotation_id, old_time)
    if type_ == 'feedback':
        return feedback_handler.save(annotation_id, old_time)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(port=8000, debug=True)
