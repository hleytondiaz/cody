from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
from flaskext.markdown import Markdown
from flaskext.mysql import MySQL
from datetime import datetime
from time import sleep
import requests

app = Flask(__name__)
mysql = MySQL()

app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_PORT'] = 3306
app.config['MYSQL_DATABASE_DB'] = 'smoj_database'
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'root'

mysql.init_app(app)
Markdown(app)

email = 'hugo.leyton@sansano.usm.cl'
categories = [
    ['programas-secuenciales', 'Programas Secuenciales'],
    ['condicionales', 'Condicionales'],
    ['ciclos', 'Ciclos'],
    ['Strings', 'strings'],
    ['funciones', 'Funciones'],
    ['listas', 'Listas'],
    ['tuplas', 'Tuplas'],
    ['diccionarios', 'Diccionarios']
]
ip_judge0 = '18.118.22.172'
port_judge0 = '2358'
url_judge0 = 'http://' + ip_judge0 + ':' + port_judge0

def check_quiz_attempted(cursor, email, category):
    cursor.execute('SELECT COUNT(*) FROM quiz_attempts WHERE email = %(email)s AND category = %(cat)s;', { 'email': email, 'cat': category})
    total_attempts = cursor.fetchone()[0]
    return total_attempts > 0

def get_category_index(categories, category):
    for i in range(len(categories)):
        if categories[i][0] == category:
            return i + 1

@app.route('/')
def index():
    conn = mysql.connect()
    cursor = conn.cursor()
    progress_list = []
    disablements = []
    for i in range(1, len(categories) + 1):
        disablements.append(check_quiz_attempted(cursor, email, i))
    return render_template('index.html', categories=categories, disablements=disablements)

@app.route('/quizzes/<string:category>', methods=['GET', 'POST'])
def quiz(category=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    category_index = get_category_index(categories, category)
    category_not_formatted, quiz_category = categories[category_index - 1]
    questions = []
    quiz_done = False

    if request.method == 'GET':
        if check_quiz_attempted(cursor, email, category_index):
            quiz_done = True
        else:
            cursor.execute('(SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 1 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 2 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 3 ORDER BY RAND() LIMIT 3);', { 'cat': category_index })
            quiz = cursor.fetchall()
            for i in range(len(quiz)):
                id_quiz_question, question = quiz[i]
                cursor.execute('SELECT id_alternative, description FROM quiz_alternatives WHERE id_question = %(id)s ORDER BY RAND();', { 'id': id_quiz_question })
                alternatives = cursor.fetchall()
                questions.append([i + 1, id_quiz_question, question, alternatives])

    if request.method == 'POST':
        if check_quiz_attempted(cursor, email, category_index):
            quiz_done = True
        else:
            total_score = 0.0
            scores = {
                1: 0.055,
                2: 0.117,
                3: 0.161
            }
            data = request.form.to_dict()
            cont = 0
            
            for q in data:
                id_question = q.split('-')[1]
                cursor.execute('SELECT level, id_correct_alternative FROM quiz_questions WHERE id_question = %(id)s;', { 'id': id_question })
                level, id_correct_alternative = cursor.fetchone()
                comp = int(data[q]) == id_correct_alternative
                cont += int(comp)
                total_score += scores[level] if comp else 0.0

            distribution = [1, 1, 1]
            final_level_str = ''
            final_level_int = 0

            if total_score < 0.33:
                final_level_str = 'BÁSICO'
                final_level_int = 1
                distribution[0] += 1
            elif total_score < 0.66:
                final_level = 'MEDIO'
                final_level_int = 2
                distribution[1] += 1
            else:
                final_level = 'AVANZADO'
                final_level_int = 3
                distribution[2] += 1
            
            final_percentage = round(cont * 100 / 9)
            insert_stmt = 'INSERT INTO quiz_attempts (email, score_obtained, attempt_date, category) VALUES (%s, %s, %s, %s)'
            data = (email, total_score, datetime.now(), category_index)
            cursor.execute(insert_stmt, data)
            conn.commit()

            cursor.execute('(SELECT id_problem FROM problems WHERE category=%(cat)s AND level=1 ORDER BY RAND() LIMIT %(d1)s) UNION (SELECT id_problem FROM problems WHERE category=%(cat)s AND level=2 ORDER BY RAND() LIMIT %(d2)s) UNION (SELECT id_problem FROM problems WHERE category=%(cat)s AND level=3 ORDER BY RAND() LIMIT %(d3)s);', { 'cat': category_index, 'd1': distribution[0], 'd2': distribution[1], 'd3': distribution[2] })
            problem_ids = cursor.fetchall()

            id_problem_1 = problem_ids[0][0]
            id_problem_2 = problem_ids[1][0]
            id_problem_3 = problem_ids[2][0]
            id_problem_4 = problem_ids[3][0]

            insert_stmt = 'INSERT INTO distribution (email, category, level, id_problem_1, id_problem_2, id_problem_3, id_problem_4) VALUES (%s, %s, %s, %s, %s, %s, %s)'
            data = (email, category_index, final_level_int, id_problem_1, id_problem_2, id_problem_3, id_problem_4)
            cursor.execute(insert_stmt, data)
            conn.commit()

            return render_template('quiz_done.html', final_level=final_level_str, final_percentage=final_percentage, quiz_category=quiz_category, category_not_formatted=category_not_formatted)
    return render_template('quiz.html', questions=questions, quiz_category=quiz_category, quiz_done=quiz_done)

@app.route('/exercises/<string:category>')
@app.route('/exercises/<string:category>/<int:id_exercise>')
def exercises(category=None, id_exercise=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    category_index = get_category_index(categories, category)
    quiz_attempted = check_quiz_attempted(cursor, email, category_index)
    if category and id_exercise:
        cursor.execute('SELECT id_problem, title, statement FROM problems WHERE id_problem = %(id_pro)s AND category = %(cat)s;', { 'id_pro': id_exercise, 'cat': category_index })
        problem_data = cursor.fetchone()
        cursor.execute('SELECT input_description, output_description, observations, notes_examples FROM subproblems WHERE id_problem=%(id_pro)s AND subproblem=1;', { 'id_pro': id_exercise })
        subproblem_data = cursor.fetchone()
        cursor.execute('SELECT stdin, expected_output FROM test_cases WHERE id_problem = %(id_pro)s AND subproblem = 1 AND sample = 1 ORDER BY id_test_case ASC;', { 'id_pro': id_exercise })
        tests_cases_data = cursor.fetchall()
        return render_template('exercise.html', problem_data=problem_data, subproblem_data=subproblem_data, tests_cases_data=tests_cases_data, category=category)
    else:
        cursor.execute('SELECT id_problem_1, id_problem_2, id_problem_3, id_problem_4, progress_p1, progress_p2, progress_p3, progress_p4, (SELECT title FROM problems WHERE problems.id_problem=id_problem_1) AS title_1, (SELECT title FROM problems WHERE problems.id_problem=id_problem_2) AS title_2, (SELECT title FROM problems WHERE problems.id_problem=id_problem_3) AS title_3, (SELECT title FROM problems WHERE problems.id_problem=id_problem_4) AS title_4, (SELECT level FROM problems WHERE problems.id_problem=id_problem_1) AS level_1, (SELECT level FROM problems WHERE problems.id_problem=id_problem_2) AS level_2, (SELECT level FROM problems WHERE problems.id_problem=id_problem_3) AS level_3, (SELECT level FROM problems WHERE problems.id_problem=id_problem_4) AS level_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': email, 'cat': category_index })
        
        problem_ids = cursor.fetchall()
        exercises = []

        for i in range(4):
            _id = problem_ids[0][i]
            progress = problem_ids[0][i + 4]
            title = problem_ids[0][i + 8]
            level = ''
            if problem_ids[0][i + 12] == 1:
                level = 'FÁCIL'
            elif problem_ids[0][i + 12] == 2:
                level = 'MEDIO'
            else:
                level = 'DIFÍCIL'
            exercises.append([_id, progress, title, level])

        return render_template('exercises.html', exercises=exercises, exercise_category=category, quiz_attempted=quiz_attempted)

@app.route('/submit', methods=['POST'])
def submit():
    body = request.get_json()

    if body is None:
        return 'The request body is null', 400
    
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    
    if 'source_code' not in body:
        return 'You need to specify the source_code', 400

    id_problem = body['id_problem']
    source_code = body['source_code']

    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT id_test_case, stdin, expected_output, feedback, sample FROM test_cases WHERE id_problem=%(id_pro)s AND subproblem=1 ORDER BY sample DESC, id_problem ASC;', { 'id_pro': id_problem})
    
    tests_cases = cursor.fetchall()

    data = { "submissions": [] }
    additional_data = []

    for i in range(len(tests_cases)):
        _, stdin, expected_output, feedback, sample = tests_cases[i]
        payload = {
            "language_id": 71,
            "source_code": source_code,
            "stdin": stdin,
            "expected_output": expected_output
        }
        data["submissions"].append(payload)
        additional_data.append([feedback, bool(sample)])

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.90 Safari/537.36'}
        response = requests.post(url_judge0 + '/submissions/batch', json=data, headers=headers)
        tokens = response.json()
        tokens_str = ''
        
        for i in range(len(tokens)):
            tokens_str += tokens[i]['token']
            tokens_str += ',' if i < len(tokens) - 1 else ''
        
        fields = 'stdin,stdout,stderr,status,status_id,token,expected_output'

        while True:
            response = requests.get(url_judge0 + '/submissions/batch?tokens=' + tokens_str + '&base64_encoded=false&fields=' + fields)
            data = response.json()["submissions"]
            cont = 0
            for i in range(len(data)):
                status_id = data[i]['status_id']
                cont += int(status_id == 1 or status_id == 2)
            if cont == 0:
                break
            else:
                sleep(2)

        dicc = response.json()
        i = 0
        correct = 0
        total = len(dicc['submissions'])

        for x in dicc['submissions']:
            correct += 1 if x['status_id'] == 3 else 0
            x['feedback'] = additional_data[i][0]
            x['sample'] = additional_data[i][1]
            if x['feedback'] == '':
                x['feedback'] = None
            if not x['sample']:
                x['stdin'] = None
                x['stdout'] = None
                x['expected_output'] = None
            i += 1

        status = 0

        if correct == 0:
            status = 1
        elif correct < total:
            status = 2
        else:
            status = 3

        progress = 1 # -1: back, 0: keep, 1: advance

        dicc['details'] = {
            'status': status,
            'progress': progress,
            'percentage_correct': round(100 * correct / total, 2)
        }

        return dicc, 200
    except:
        return 'Judgment error', response.status_code