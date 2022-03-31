from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
from flask import session
from flask import redirect
from flask import url_for
from flaskext.mysql import MySQL
from datetime import datetime
from time import sleep
from flask_cors import CORS
from pylti.flask import lti
import markdown
import requests
import settings
import os

app = Flask(__name__)
mysql = MySQL()
cors = CORS(app, resources={r'/api/*': {'origins': '*'}})

app.config['MYSQL_DATABASE_HOST'] = os.environ.get('MYSQL_DATABASE_HOST')
app.config['MYSQL_DATABASE_PORT'] = int(os.environ.get('MYSQL_DATABASE_PORT'))
app.config['MYSQL_DATABASE_DB'] = os.environ.get('MYSQL_DATABASE_DB')
app.config['MYSQL_DATABASE_USER'] = os.environ.get('MYSQL_DATABASE_USER')
app.config['MYSQL_DATABASE_PASSWORD'] = os.environ.get('MYSQL_DATABASE_PASSWORD')

'''
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_PORT'] = 3306
app.config['MYSQL_DATABASE_DB'] = 'smoj_database'
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'root'
'''

app.secret_key = settings.secret_key
app.config.from_object(settings.configClass)

mysql.init_app(app)

#email = 'hugo.leyton@sansano.usm.cl'
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
ip_judge0 = '54.207.151.47'
port_judge0 = '2358'
#ip_judge0 = os.environ.get('JUDGE0_HOST')
#port_judge0 = os.environ.get('JUDGE0_PORT')
url_judge0 = 'http://' + ip_judge0 + ':' + port_judge0

def check_quiz_attempted(cursor, email, category):
    cursor.execute('SELECT COUNT(*) FROM quiz_attempts WHERE email = %(email)s AND category = %(cat)s;', { 'email': email, 'cat': category })
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
    progress = []
    for i in range(1, len(categories) + 1):
        if 'user'in session:
            # obtener nivel (basico, medio, alto) de la categoria
            cursor.execute('SELECT level, id_problem_1, id_problem_2, id_problem_3, id_problem_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': session['user'], 'cat': i })
            details = cursor.fetchone()
            level = 0
            mean = 0.0
            if details != None:
                problem_ids = [x for x in details[1:]]
                level, id_problem_1, id_problem_2, id_problem_3, id_problem_4 = details
                sum_ = 0
                for id_problem in problem_ids:
                    cursor.execute('SELECT MAX(score) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND valid=1;', { 'id_pro': id_problem, 'email': session['user'] })
                    score = cursor.fetchone()[0]
                    score = 0.0 if score == None else score
                    sum_ += 1.0 if score == 100 else 0.0
                mean = round((sum_ / 4) * 100, 2)
            progress.append([level, mean])
            disablements.append(check_quiz_attempted(cursor, session['user'], i))
    print(progress)
    return render_template('index.html', categories=categories, disablements=disablements, progress=progress)

@app.route('/quizzes/<string:category>', methods=['GET', 'POST'])
def quiz(category=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    category_index = get_category_index(categories, category)
    category_not_formatted, quiz_category = categories[category_index - 1]
    questions = []
    quiz_done = False

    if request.method == 'GET':
        if check_quiz_attempted(cursor, session['user'], category_index):
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
        if check_quiz_attempted(cursor, session['user'], category_index):
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
            data = (session['user'], total_score, datetime.now(), category_index)
            cursor.execute(insert_stmt, data)
            conn.commit()

            cursor.execute('(SELECT id_problem FROM problems WHERE category=%(cat)s AND level=1 ORDER BY RAND() LIMIT %(d1)s) UNION (SELECT id_problem FROM problems WHERE category=%(cat)s AND level=2 ORDER BY RAND() LIMIT %(d2)s) UNION (SELECT id_problem FROM problems WHERE category=%(cat)s AND level=3 ORDER BY RAND() LIMIT %(d3)s);', { 'cat': category_index, 'd1': distribution[0], 'd2': distribution[1], 'd3': distribution[2] })
            problem_ids = cursor.fetchall()

            id_problem_1 = problem_ids[0][0]
            id_problem_2 = problem_ids[1][0]
            id_problem_3 = problem_ids[2][0]
            id_problem_4 = problem_ids[3][0]

            insert_stmt = 'INSERT INTO distribution (email, category, level, id_problem_1, id_problem_2, id_problem_3, id_problem_4) VALUES (%s, %s, %s, %s, %s, %s, %s)'
            data = (session['user'], category_index, final_level_int, id_problem_1, id_problem_2, id_problem_3, id_problem_4)
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
    quiz_attempted = check_quiz_attempted(cursor, session['user'], category_index)
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
        return render_template('exercise.html', url_judge0=url_judge0, problem_data=problem_data, subproblem_data=subproblem_data, tests_cases_data=tests_cases_data, category=category)
    else:
        cursor.execute('SELECT id_problem_1, id_problem_2, id_problem_3, id_problem_4, (SELECT title FROM problems WHERE problems.id_problem=id_problem_1) AS title_1, (SELECT title FROM problems WHERE problems.id_problem=id_problem_2) AS title_2, (SELECT title FROM problems WHERE problems.id_problem=id_problem_3) AS title_3, (SELECT title FROM problems WHERE problems.id_problem=id_problem_4) AS title_4, (SELECT level FROM problems WHERE problems.id_problem=id_problem_1) AS level_1, (SELECT level FROM problems WHERE problems.id_problem=id_problem_2) AS level_2, (SELECT level FROM problems WHERE problems.id_problem=id_problem_3) AS level_3, (SELECT level FROM problems WHERE problems.id_problem=id_problem_4) AS level_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': session['user'], 'cat': category_index })
        
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
            cursor.execute('SELECT MAX(score) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND valid=True;', { 'id_pro': _id, 'email': session['user'] })
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
        give_feedback = 0

        cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND score=100 AND valid=True;', { 'id_pro': id_problem, 'email': session['user'] })
        problem_solved = cursor.fetchone()[0]

        if problem_solved == 0:
            tokens = ','.join(list_tokens)
            insert_stmt = 'INSERT INTO submission_2 (id_problem, email, source_code, score, datetime, tokens, valid) VALUES (%s, %s, %s, %s, %s, %s, %s)'
            data = (id_problem, session['user'], source_code, percentage_correct, datetime.now(), tokens, True)
            cursor.execute(insert_stmt, data)
            conn.commit()

            cursor.execute('SELECT category FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_problem })
            category_index = cursor.fetchone()[0]

            cursor.execute('SELECT level, id_problem_1, id_problem_2, id_problem_3, id_problem_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC;', { 'email': session['user'], 'cat': category_index })
            current_distribution = cursor.fetchone() # esto fallara si no tiene una distribucion
            current_level = current_distribution[0]
            problem_ids = [x for x in current_distribution[1:]]
            current_progress = {1: [0, 0], 2: [0, 0], 3: [0, 0]} # { level: [problems completely solved, total attempts minus problems completely solved] }

            for i in range(len(problem_ids)):
                id_ = problem_ids[i]
                cursor.execute('SELECT MAX(score), COUNT(*) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND valid=True;', { 'id_pro': id_, 'email': session['user'] })
                score, attempts = cursor.fetchone()
                score = 0.0 if score == None else score
                cursor.execute('SELECT level FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_ })
                level = cursor.fetchone()[0]
                current_progress[level][0] += 1 if score == 100 else 0
                current_progress[level][1] += attempts - 1 if score == 100 else attempts

            total_problems_solved = current_progress[1][0] + current_progress[2][0] + current_progress[3][0]
            total_attempts = current_progress[1][1] + current_progress[2][1] + current_progress[3][1]

            if current_level == 1:
                if current_progress[1][0] == 2 or current_progress[2][0] == 1 or current_progress[2][0] == 1:
                    progress = 1
                elif total_problems_solved == 0 and total_attempts == 8:
                    progress = -2
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

            if progress in [-2, -1, 1, 3]:
                if progress == -1:
                    new_level = 1 if current_level == 1 else current_level - 1
                elif progress == 1:
                    new_level = 3 if current_level == 3 else current_level + 1
                else:
                    new_level = current_level

                new_distribution = []

                if new_level == 1:
                    new_distribution = [2, 1, 1]
                elif new_level == 2:
                    new_distribution = [1, 2, 1]
                else:
                    new_distribution = [1, 1, 2]

                cursor.execute('SELECT DISTINCT(submission_2.id_problem) FROM submission_2 JOIN problems ON submission_2.id_problem = problems.id_problem WHERE submission_2.email=%(email)s AND submission_2.score=100 AND problems.category=%(cat)s;', { 'email': session['user'], 'cat': category_index })

                problem_ids = [str(x[0]) for x in cursor.fetchall()]
                pro_set = ','.join(problem_ids)

                ids_list = []

                for i in range(len(new_distribution)):
                    level = i + 1
                    limit = new_distribution[i]
                    if len(ids_list) > 0:
                        cursor.execute('SELECT id_problem FROM problems WHERE category=%(cat)s AND level=%(lvl)s AND id_problem NOT IN (' + pro_set + ') LIMIT %(lim)s;', { 'cat': category_index, 'lvl': level, 'lim': limit })
                    else:
                        cursor.execute('SELECT id_problem FROM problems WHERE category=%(cat)s AND level=%(lvl)s LIMIT %(lim)s;', { 'cat': category_index, 'lvl': level, 'lim': limit })
                    ids = cursor.fetchall()
                    pro_set = ','.join([str(x[0]) for x in ids])

                    if len(ids) < limit:
                        amount = limit - len(ids)
                        cursor.execute('SELECT id_problem FROM problems WHERE category=%(cat)s AND level=%(lvl)s AND id_problem NOT IN (' + pro_set + ') LIMIT %(lim)s;', { 'cat': category_index, 'lvl': level, 'lim': amount })
                        ids_list += [x[0] for x in cursor.fetchall()]
                    
                    ids_list += [x[0] for x in ids]
                
                '''
                print('current_progress:', current_progress)
                print('current_level:', current_level)
                print('new_level:', new_level)
                print('new_distribution:', new_distribution)
                print('email:', email)
                print('cat:', category_index)
                print('problem_ids:', problem_ids)
                print('pro_set:', pro_set)
                print('ids_list', ids_list)
                '''
                
                id_problem_1, id_problem_2, id_problem_3, id_problem_4 = ids_list

                insert_stmt = 'INSERT INTO distribution (email, category, level, id_problem_1, id_problem_2, id_problem_3, id_problem_4) VALUES (%s, %s, %s, %s, %s, %s, %s)'
                data = (session['user'], category_index, new_level, id_problem_1, id_problem_2, id_problem_3, id_problem_4)
                cursor.execute(insert_stmt, data)
                conn.commit()

                cursor.execute('UPDATE submission_2 SET valid=0 WHERE email=%(email)s;', { 'email': session['user'] })
                conn.commit()
        else:
            progress = 2
        
        if problem_solved or status == 3:
            cursor.execute('SELECT COUNT(*) FROM feedback WHERE id_problem=%(id_pro)s AND email=%(email)s;', { 'id_pro': id_problem, 'email': session['user'] })
            give_feedback = 1 if cursor.fetchone()[0] == 0 else 0

        dicc['details'] = {
            'status': status,
            'progress': progress,
            'percentage_correct': percentage_correct,
            'give_feedback': give_feedback
        }

        return dicc, 200
    except Exception as e:
        print(e)
        return 'Judgment error', 400

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    sleep(1)

    body = request.get_json()

    if body is None:
        return 'The request body is null', 400
    
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    
    if 'checked_option' not in body:
        return 'You need to specify the checked_option', 400

    id_problem = body['id_problem']
    checked_option = body['checked_option']
    
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(score) FROM submission_2 WHERE email=%(email)s AND id_problem=%(id_pro)s AND valid=1;', { 'email': session['user'], 'id_pro': id_problem })
        score = cursor.fetchone()[0]
        if score == 100:
            insert_stmt = 'INSERT INTO feedback (id_problem, email, level, status, datetime) VALUES (%s, %s, %s, %s, %s)'
            data = (id_problem, session['user'], checked_option, True, datetime.now())
            cursor.execute(insert_stmt, data)
            conn.commit()
            return { 'message': 'ok' }, 200
        else:
            return { 'message': 'no_ok' }, 200
    else:
        return { 'message': 'no_ok' }, 200

@app.route('/launch', methods=['POST'])
@lti(request='initial', role='any', app=app)
def launch(lti=lti):
    session['user'] = request.form.get('lis_person_contact_email_primary')
    return redirect(url_for('index'))

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/helloworld', methods=['GET'])
def helloworld():
    return "<h1>Hello World!</h1>"