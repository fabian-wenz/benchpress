import json

with open("config.json", "r") as _f:
    DATA = json.load(_f)

DATABASE = DATA['datasets'][0]
TASK = DATA['tasks'][0]
MODEL = DATA['models'][0]
REL_TABLES = []
REL_EXAMPLES = []
PROMPT = DATA['prompt']
PROMPT_TXT = DATA['prompt_text']
SQL_FILE = "./data/{DATABASE}/queries"
SCHEMA_FILE = "./data/{DATABASE}/tables"
SCHEMA_FOLDER = "./data/{DATABASE}/schema/"
OVERALL_TIME = ""
SINGLE_TIME = ""
USER_NAME = ""
API_KEY = ""
