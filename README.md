# smoj-flask

### Windows

py -3 -m venv venv

venv\Scripts\activate

set FLASK_APP=app/app.py

set FLASK_ENV=development

flask run

#### Linux and macOS

python3 -m venv venv

. venv/bin/activate

export FLASK_APP=app/app.py

export FLASK_ENV=development

flask run