import os
from flask import json


def load_json_data(file_name):
    with open(file_name + '.json', 'r') as f:
        data = json.load(f)
    return data


def save_json_data(file_name, data):
    with open(file_name + '.json', 'w') as f:
        json.dump(data, f, indent=4)


def retrieve_filenames(folder_path):
    files = []
    for filename in os.listdir(folder_path):
        name, extension = os.path.splitext(filename)
        files.append(name)
    return files
