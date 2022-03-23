from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
from flaskext.mysql import MySQL
from datetime import datetime
from time import sleep
from flask_cors import CORS
from pylti.flask import lti
import markdown
import requests
import settings

app = Flask(__name__)
mysql = MySQL()
cors = CORS(app, resources={r'/api/*': {'origins': '*'}})

app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_PORT'] = 3306
app.config['MYSQL_DATABASE_DB'] = 'smoj_database'
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'root'

app.secret_key = settings.secret_key
app.config.from_object(settings.configClass)

mysql.init_app(app)

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
                question = markdown.markdown(question)
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
        id_problem, title, statement = cursor.fetchone()
        html = markdown.markdown(statement, extensions=['tables'])
        problem_data = (id_problem, title, html)
        cursor.execute('SELECT input_description, output_description, observations, notes_examples FROM subproblems WHERE id_problem=%(id_pro)s AND subproblem=1;', { 'id_pro': id_exercise })
        input_description, output_description, observations, notes_examples = cursor.fetchone()
        input_description = markdown.markdown(input_description, extensions=['tables'])
        output_description = markdown.markdown(output_description, extensions=['tables'])
        observations = markdown.markdown(observations, extensions=['tables'])
        notes_examples = markdown.markdown(notes_examples, extensions=['tables'])
        subproblem_data = (input_description, output_description, observations, notes_examples)
        cursor.execute('SELECT stdin, expected_output FROM test_cases WHERE id_problem = %(id_pro)s AND subproblem = 1 AND sample = 1 ORDER BY id_test_case ASC;', { 'id_pro': id_exercise })
        tests_cases_data = cursor.fetchall()
        return render_template('exercise.html', problem_data=problem_data, subproblem_data=subproblem_data, tests_cases_data=tests_cases_data, category=category)
    else:
        cursor.execute('SELECT id_problem_1, id_problem_2, id_problem_3, id_problem_4, (SELECT title FROM problems WHERE problems.id_problem=id_problem_1) AS title_1, (SELECT title FROM problems WHERE problems.id_problem=id_problem_2) AS title_2, (SELECT title FROM problems WHERE problems.id_problem=id_problem_3) AS title_3, (SELECT title FROM problems WHERE problems.id_problem=id_problem_4) AS title_4, (SELECT level FROM problems WHERE problems.id_problem=id_problem_1) AS level_1, (SELECT level FROM problems WHERE problems.id_problem=id_problem_2) AS level_2, (SELECT level FROM problems WHERE problems.id_problem=id_problem_3) AS level_3, (SELECT level FROM problems WHERE problems.id_problem=id_problem_4) AS level_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': email, 'cat': category_index })
        
        problem_ids = cursor.fetchall()
        exercises = []

        for i in range(4):
            _id = problem_ids[0][i]
            title = problem_ids[0][i + 4]
            level = ''
            if problem_ids[0][i + 8] == 1:
                level = 'FÁCIL'
            elif problem_ids[0][i + 8] == 2:
                level = 'MEDIO'
            else:
                level = 'DIFÍCIL'
            cursor.execute('SELECT MAX(score) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND valid=True;', { 'id_pro': _id, 'email': email })
            score = cursor.fetchone()[0]
            score = 0 if score == None else round(score, 2)
            exercises.append([_id, title, level, score])

        return render_template('exercises.html', exercises=exercises, exercise_category=category, quiz_attempted=quiz_attempted)

@app.route('/api/submit', methods=['POST'])
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
        list_tokens = []

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
            list_tokens.append(x['token'])
            i += 1

        status = 0

        if correct == 0:
            status = 1
        elif correct < total:
            status = 2
        else:
            status = 3

        '''
        progress =
            -2: all the problems tried and not solved, 
            -1: back, 
            0 : keep, 
            1 : advance, 
            2 : problem solved, 
            3 : problem set solved
        '''
        progress = None 
        percentage_correct = round(100 * correct / total, 2)

        cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND score=100 AND valid=True;', { 'id_pro': id_problem, 'email': email })
        problem_solved = cursor.fetchone()[0]

        if problem_solved == 0:
            tokens = ','.join(list_tokens)
            insert_stmt = 'INSERT INTO submission_2 (id_problem, email, source_code, score, datetime, tokens, valid) VALUES (%s, %s, %s, %s, %s, %s, %s)'
            data = (id_problem, email, source_code, percentage_correct, datetime.now(), tokens, True)
            cursor.execute(insert_stmt, data)
            conn.commit()

            cursor.execute('SELECT category FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_problem })
            category_index = cursor.fetchone()[0]

            cursor.execute('SELECT level, id_problem_1, id_problem_2, id_problem_3, id_problem_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC;', { 'email': email, 'cat': category_index })
            current_distribution = cursor.fetchone()
            current_level = current_distribution[0]
            problem_ids = [x for x in current_distribution[1:]]
            current_progress = {1: [0, 0], 2: [0, 0], 3: [0, 0]} # { level: [problems completely solved, total attempts minus problems completely solved] }

            for i in range(len(problem_ids)):
                id_ = problem_ids[i]
                cursor.execute('SELECT MAX(score), COUNT(*) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND valid=True;', { 'id_pro': id_, 'email': email })
                score, attempts = cursor.fetchone()
                score = 0.0 if score == None else score
                cursor.execute('SELECT level FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_ })
                level = cursor.fetchone()[0]
                current_progress[level][0] += 1 if score == 100 else 0
                current_progress[level][1] += attempts - 1 if score == 100 else attempts

            if current_level == 1:
                if current_progress[1][0] == 2 or current_progress[2][0] == 1 or current_progress[2][0] == 1:
                    progress = 1
                else:
                    progress = 0
            elif current_level == 2:
                if current_progress[2][0] == 2 or current_progress[3][0] == 1:
                    progress = 1
                elif current_progress[1][1] == 2 or current_progress[2][1] == 4 or current_progress[3][1] == 4:
                    progress = -1
                else:
                    progress = 0
            else:
                if current_progress[1][0] + current_progress[2][0] + current_progress[3][0] == 4:
                    progress = 3
                elif current_progress[1][1] == 2 or current_progress[2][1] == 2 or current_progress[3][1] == 4:
                    progress = -1
                else:
                    progress = 0

            if progress == -1 or progress == 1 or progress == 3:
                if progress == -1:
                    new_level = 1 if current_level == 1 else current_level - 1
                elif progress == 1:
                    new_level = 3 if current_level == 3 else current_level + 1
                else:
                    new_level = current_level

                distribution = []

                if new_level == 1:
                    distribution = [2, 1, 1]
                elif new_level == 2:
                    distribution = [1, 2, 1]
                else:
                    distribution = [1, 1, 2]

                print('current_progress:', current_progress)
                print('current_level:', current_level)
                print('new_level:', new_level)
                print('distribution:', distribution)

                cursor.execute('SELECT DISTINCT(submission_2.id_problem) FROM submission_2 JOIN problems ON submission_2.id_problem = problems.id_problem WHERE submission_2.email=%(email)s AND submission_2.score=100 AND problems.category=%(cat)s;', { 'email': email, 'cat': category_index })
                problem_ids = [x[0] for x in cursor.fetchall()]

                for i in range(len(distribution)):
                    level = i + 1
                    limit = distribution[i]
                    #cursor.execute('SELECT id_problem FROM problems WHERE category=%(cat)s AND level=%(lvl)s AND id_problem NOT IN %(pro_set) LIMIT %(limit)s;', { 'cat': category_index, 'lvl': level, 'pro_set': })
        else:
            progress = 2

        dicc['details'] = {
            'status': status,
            'progress': progress,
            'percentage_correct': percentage_correct
        }

        return dicc, 200
    except:
        return 'Judgment error', response.status_code

@app.route('/launch', methods=['POST', 'GET'])
@lti(request='initial', role='any', app=app)
def launch(lti=lti):
    print('lis_person_name_full:')
    print(request.form.get('lis_person_name_full'))
    return request.form.get('lis_person_name_full')





