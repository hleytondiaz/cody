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

export FLASK_RUN_HOST=0.0.0.0

export FLASK_RUN_PORT=8080

flask run