import json
import random
from pathlib import Path

from flask import render_template, request, redirect, url_for, jsonify

import handlers.state as state


def _index():
    return render_template('index.html')


def _submit():
    api_key = request.form.get("api_key")
    user_id = request.form.get("user_id")
    sql_file = request.files.get("sql_file")

    state.API_KEY = api_key
    state.USER_NAME = user_id

    if sql_file:
        sql_file.save(f"./{sql_file.filename}")
        if state.API_KEY != "":
            state.SQL_FILE = sql_file[:-4]

    print(f"Username: {user_id}")

    file_path = Path("./data/user/queries_" + user_id + '.json')
    if not file_path.exists():
        with open(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()) + '.json', 'r') as f_in, \
                open("./data/user/queries_" + user_id + '.json', 'w') as f_out:
            f_out.write(f_in.read())
    state.SQL_FILE = "./data/user/queries_" + user_id

    return redirect(url_for("index"))


def _save_api_key_and_user_id():
    CONFIG_FILE = "config.json"

    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    else:
        config = {}

    data = request.json
    api_key = data.get("api_key")
    user_id = data.get("user_id")

    if not api_key:
        return jsonify({"message": "API Key is missing!"}), 400

    state.API_KEY = api_key
    print("Received API Key:", state.API_KEY)

    config["api_key"] = api_key
    config["user_id"] = user_id
    config["database"] = state.DATABASE
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    file_path = Path(state.SQL_FILE.format(DATABASE=state.DATABASE.lower()) + ".json")
    output_path = Path("./data/user/queries_" + user_id + ".json")

    if not output_path.exists():
        with open(file_path, "r") as f_in:
            data = json.load(f_in)

        first_15 = data[:15]
        last_15 = data[-15:]

        random.shuffle(first_15)
        random.shuffle(last_15)

        new_data = first_15 + last_15

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f_out:
            json.dump(new_data, f_out, indent=2)

    state.SQL_FILE = "./data/user/queries_" + user_id

    return jsonify({"message": "API Key saved successfully!"})
