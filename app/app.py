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
from dotenv import load_dotenv
from dotenv import find_dotenv
from base64 import b64decode
from flask_apscheduler import APScheduler
import markdown
import requests
import settings
import os
import time

load_dotenv(find_dotenv())

app = Flask(__name__)
mysql = MySQL()
cors = CORS(app, resources={r'/api/*': {'origins': '*'}})
#scheduler = APScheduler()

app.config['MYSQL_DATABASE_HOST'] = os.environ.get('MYSQL_DATABASE_HOST')
app.config['MYSQL_DATABASE_PORT'] = int(os.environ.get('MYSQL_DATABASE_PORT'))
app.config['MYSQL_DATABASE_DB'] = os.environ.get('MYSQL_DATABASE_DB')
app.config['MYSQL_DATABASE_USER'] = os.environ.get('MYSQL_DATABASE_USER')
app.config['MYSQL_DATABASE_PASSWORD'] = os.environ.get('MYSQL_DATABASE_PASSWORD')

app.secret_key = os.environ.get('SECRET_FLASK')
app.config.from_object(settings.configClass)

mysql.init_app(app)

categories = [
    ['programas-secuenciales', 'Programas Secuenciales'],
    ['condicionales', 'Condicionales'],
    ['ciclos', 'Ciclos'],
    ['strings', 'Strings'],
    ['funciones', 'Funciones'],
    ['listas', 'Listas'],
    ['tuplas', 'Tuplas'],
    ['diccionarios', 'Diccionarios']
]

ip_judge0 = os.environ.get('JUDGE0_HOST')
port_judge0 = os.environ.get('JUDGE0_PORT')
url_judge0 = 'http://' + ip_judge0 + ':' + port_judge0

def check_quiz_attempted(cursor, email, category):
    cursor.execute('SELECT COUNT(*) FROM quiz_attempts WHERE email = %(email)s AND category = %(cat)s;', { 'email': email, 'cat': category })
    total_attempts = cursor.fetchone()[0]
    return total_attempts > 0

def get_category_index(categories, category):
    for i in range(len(categories)):
        if categories[i][0] == category:
            return i + 1

def modified_b64decode(string):
    if string != None:
        if len(string) > 0:
            return b64decode(string).decode('utf-8')
        else:
            return ''
    else:
        return None

@app.route('/')
def index():
    conn = mysql.connect()
    cursor = conn.cursor()
    statistics = []
    tables = ['problems', 'submission_2', 'users']
    for t in tables:
        cursor.execute('SELECT COUNT(*) FROM ' + t + ';')
        statistics.append(cursor.fetchone()[0])
    current_year = datetime.now().year
    page_title = 'Inicio'
    return render_template('index.html', page_title=page_title, statistics=statistics, current_year=current_year)

@app.route('/quizzes/<string:category>', methods=['GET', 'POST'])
def quiz(category=None):
    if 'user' not in session:
        return render_template('not_authorized.html', page_title='Acceso denegado')

    conn = mysql.connect()
    cursor = conn.cursor()
    category_index = get_category_index(categories, category)
    category_not_formatted, quiz_category = categories[category_index - 1]
    questions = []
    quiz_done = False

    page_title = 'Quiz ' + quiz_category

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
                final_level_str = 'MEDIO'
                final_level_int = 2
                distribution[1] += 1
            else:
                final_level_str = 'AVANZADO'
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

            insert_stmt = 'INSERT INTO distribution (email, category, level, id_problem_1, id_problem_2, id_problem_3, id_problem_4, datetime) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
            data = (session['user'], category_index, final_level_int, id_problem_1, id_problem_2, id_problem_3, id_problem_4, datetime.now())
            cursor.execute(insert_stmt, data)
            conn.commit()

            return render_template('quiz_done.html', page_title=page_title, final_level=final_level_str, final_percentage=final_percentage, quiz_category=quiz_category, category_not_formatted=category_not_formatted)
    return render_template('quiz.html', page_title=page_title, questions=questions, quiz_category=quiz_category, quiz_done=quiz_done)

@app.route('/exercises')
@app.route('/exercises/<string:category>')
@app.route('/exercises/<string:category>/<int:id_exercise>')
def exercises(category=None, id_exercise=None):
    if 'user' not in session:
        return render_template('not_authorized.html', page_title='Acceso denegado')

    conn = mysql.connect()
    cursor = conn.cursor()
    
    if category == None:
        if id_exercise == None:
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
            page_title = 'Inicio'
            return render_template('categories.html', page_title=page_title, categories=categories, disablements=disablements, progress=progress)
    else:
        if category not in [cat[0] for cat in categories]:
            return 'La categoría a la que intentas acceder no existe.'

        category_index = get_category_index(categories, category)
        quiz_attempted = check_quiz_attempted(cursor, session['user'], category_index)
        
        if id_exercise == None:
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

            page_title = 'Ejercicios ' + categories[category_index][1]

            return render_template('exercises.html', page_title=page_title, exercises=exercises, exercise_category=category, quiz_attempted=quiz_attempted)
        else:
            cursor.execute('SELECT COUNT(*) FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_exercise })
            if not cursor.fetchone()[0]:
                return 'No existe ningún problema asociado al ID indicado.'
            cursor.execute('SELECT id_problem_1, id_problem_2, id_problem_3, id_problem_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': session['user'], 'cat': category_index })
            problem_allowed = id_exercise in cursor.fetchone()
            cursor.execute('SELECT id_problem, title, statement FROM problems WHERE id_problem = %(id_pro)s AND category = %(cat)s;', { 'id_pro': id_exercise, 'cat': category_index })
            id_problem, title, statement = cursor.fetchone()
            html = markdown.markdown(statement, extensions=['tables', 'fenced_code'])
            problem_data = (id_problem, title, html)
            cursor.execute('SELECT input_description, output_description, observations, notes_examples FROM subproblems WHERE id_problem=%(id_pro)s AND subproblem=1;', { 'id_pro': id_exercise })
            input_description, output_description, observations, notes_examples = cursor.fetchone()
            input_description = markdown.markdown(input_description, extensions=['tables', 'fenced_code'])
            output_description = markdown.markdown(output_description, extensions=['tables', 'fenced_code'])
            observations = markdown.markdown(observations, extensions=['tables', 'fenced_code'])
            notes_examples = markdown.markdown(notes_examples, extensions=['tables', 'fenced_code'])
            subproblem_data = (input_description, output_description, observations, notes_examples)
            cursor.execute('SELECT stdin, expected_output FROM test_cases WHERE id_problem = %(id_pro)s AND subproblem = 1 AND sample = 1 ORDER BY id_test_case ASC;', { 'id_pro': id_exercise })
            tests_cases_data = cursor.fetchall()
            page_title = title if problem_allowed else 'Error'
            return render_template('exercise.html', page_title=page_title, url_judge0=url_judge0, problem_data=problem_data, subproblem_data=subproblem_data, tests_cases_data=tests_cases_data, category=category, problem_allowed=problem_allowed)

@app.route('/progress', methods=['GET'])
def progress():
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT level FROM distribution WHERE email=%(email)s ORDER BY id_distribution ASC LIMIT 100;', { 'email': session['user'] })
    distribution_ids = [x[0] for x in cursor.fetchall()]
    enumeration = [x for x in range(1, len(distribution_ids) + 1)]
    cursor.execute('SELECT DISTINCT(id_problem) FROM submission_2 WHERE email=%(email)s AND score=100;', { 'email': session['user'] })
    problem_ids = [str(x[0]) for x in cursor.fetchall()]
    pro_set = ','.join(problem_ids)
    cursor.execute('SELECT DISTINCT(id_problem) FROM submission_2 WHERE email=%(email)s AND id_problem NOT IN (' + pro_set + ');', { 'email': session['user'] })
    unsolved_problems = cursor.fetchall()
    cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE email=%(email)s;', { 'email': session['user'] })
    number_of_submissions = cursor.fetchone()[0]
    metrics = [len(problem_ids), len(unsolved_problems), number_of_submissions]
    amount_by_status = []
    for status_id in range(1, 15):
        cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE email=%(email)s AND verdict_id=%(verdict)s;', { 'email': session['user'], 'verdict': status_id })
        amount_by_status.append(cursor.fetchone()[0])
    amount_by_status[6] += sum(amount_by_status[7:12])
    categories_aux = [x for x in categories]
    for i in range(len(categories_aux)):
        categories_aux[i][0] = i + 1
    page_title = 'Progreso'
    return render_template('progress.html', page_title=page_title, categories=categories_aux, distribution_ids=distribution_ids, enumeration=enumeration, metrics=metrics, amount_by_status=amount_by_status)

@app.route('/profile', methods=['GET'])
def profile():
    if 'user' not in session:
        return render_template('not_authorized.html', page_title='Acceso denegado')

    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id_user=%(user)s', { 'user': session['user'] })
    profile_data = [x for x in cursor.fetchall()[0]]
    profile_data.append('Estudiante' if session['role'] == 'learner' else 'Profesor')
    cursor.execute('SELECT id_group FROM `groups` ORDER BY id_group ASC;')
    groups = [x[0] for x in cursor.fetchall()]
    cursor.execute('SELECT badges.id_badge, badges.description, badges.bg_color, badges_users.datetime FROM badges JOIN badges_users ON badges_users.id_badge=badges.id_badge WHERE badges_users.email=%(email)s ORDER BY badges_users.datetime DESC;', { 'email': session['user'] })
    badges = cursor.fetchall()
    page_title = 'Perfil'
    return render_template('profile.html', page_title=page_title, profile_data=profile_data, groups=groups, badges=badges)

@app.route('/survey', methods=['GET', 'POST'])
def survey():
    if 'user' not in session:
        return render_template('not_authorized.html', page_title='Acceso denegado')
    
    status = 'SURVEY_NOT_ANSWERED'
    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM survey_answers WHERE email=%(email)s', { 'email': session['user'] });
    survey_answered = True if cursor.fetchone()[0] > 0 else False

    if survey_answered:
        status = 'SURVEY_ALREADY_ANSWERED'
    else:
        if request.method == 'POST':
            textarea1 = request.form['textarea1']
            textarea2 = request.form['textarea2']
            textarea3 = request.form['textarea3']
            textarea4 = request.form['textarea4']
            textarea5 = request.form['textarea5']
            status = 'SURVEY_ANSWERED'
            insert_stmt = 'INSERT INTO survey_answers (email, textarea1, textarea2, textarea3, textarea4, textarea5, datetime) VALUES (%s, %s, %s, %s, %s, %s, %s)'
            data = (session['user'], textarea1, textarea2, textarea3, textarea4, textarea5, datetime.now())
            cursor.execute(insert_stmt, data)
            conn.commit()
    page_title = 'Encuesta'
    return render_template('survey.html', page_title=page_title, status=status)

@app.route('/admin/<string:option>', methods=['GET'])
@app.route('/admin/<string:option>/<int:number>', methods=['GET'])
def admin(option=None, number=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    if option == 'exercises':
        page = number
        cursor.execute('SELECT COUNT(*) FROM problems;')
        submissions_length = cursor.fetchone()[0]
        submissions_per_page = 50
        offset = 0
        max_pages = int(submissions_length / submissions_per_page) + 1

        if page != None:
            if page >= 1 and page <= max_pages:
                offset = submissions_per_page * (page - 1)
            else:
                return redirect(url_for('admin', option='exercises'))
        
        cursor.execute('SELECT id_problem, title, category, level FROM problems ORDER BY id_problem ASC LIMIT %(lim)s OFFSET %(off)s;', { 'lim': submissions_per_page, 'off': offset })
        current_page = 1 if page == None else page
        problems = []
        max_characters = 60
        levels = ['Fácil', 'Medio', 'Difícil']
        
        for p in cursor.fetchall():
            id_problem, title, category, level = p
            title = title if len(title) <= max_characters else title[:max_characters] + '...'
            level = levels[level - 1] if level > 0 else 'Sin Nivel'
            problems.append([id_problem, title, category, level])
        page_title = 'Administración de Ejercicios'
        
        return render_template('exercises_admin.html', page_title=page_title, problems=problems, categories=categories, current_page=current_page, max_pages=max_pages)
    if option == 'groups':
        page_title = 'Administración de Paralelos'
        cursor.execute('SELECT id_group FROM `groups`;')
        groups = cursor.fetchall()

        id_group = number

        if id_group == None:
            id_group = -1
        
        add = '(' + str(id_group) + ')'
        
        if id_group == -1:
            add = '(' + ','.join([str(x[0]) for x in groups]) + ')'
        
        cursor.execute('SELECT categories.category, COUNT(*) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem JOIN categories ON categories.id_category=problems.category JOIN users ON users.id_user=submission_2.email WHERE users.id_group IN ' + add + ' GROUP BY problems.category ORDER BY categories.id_category;')
        submissions_quantity_summary = [list(x) for x in cursor.fetchall()]
        for i in range(len(submissions_quantity_summary)):
            for j in range(1, 4):
                cursor.execute('SELECT COUNT(*) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem JOIN categories ON categories.id_category=problems.category JOIN users ON users.id_user=submission_2.email WHERE categories.id_category=' + str(i + 1) + ' AND problems.level=' + str(j) + ' AND users.id_group IN ' + add + ' GROUP BY problems.category ORDER BY categories.id_category;')
                quantity = cursor.fetchone()
                submissions_quantity_summary[i].append(0 if quantity == None else quantity[0])
        
        cursor.execute('SELECT submission_2.verdict_id, COUNT(*) FROM submission_2 JOIN users ON users.id_user=submission_2.email WHERE users.id_group IN ' + add + ' GROUP BY submission_2.verdict_id ORDER BY submission_2.verdict_id;')
        submissions_by_verdict = [list(x) for x in cursor.fetchall()]
        sum_submissions = sum([x[1] for x in submissions_by_verdict])
        response = requests.get(url_judge0 + '/statuses')
        for r in response.json():
            for i in range(len(submissions_by_verdict)):
                if submissions_by_verdict[i][0] == r['id']:
                    submissions_by_verdict[i][0] = r['description']
                    if sum_submissions == 0:
                        avg = 0.0
                    else:
                        avg = round(100 * (submissions_by_verdict[i][1] / sum_submissions), 2)
                    submissions_by_verdict[i].append(avg)
        
        cursor.execute('SELECT categories.category, COUNT(*) FROM distribution JOIN categories ON categories.id_category=distribution.category JOIN users ON users.id_user=distribution.email WHERE users.id_group IN ' + add + ' GROUP BY categories.id_category ORDER BY categories.id_category ASC;')
        distributions = [list(x) for x in cursor.fetchall()]
        
        for i in range(1, 4):
            cursor.execute('SELECT COUNT(*) FROM distribution JOIN categories ON categories.id_category=distribution.category JOIN users ON users.id_user=distribution.email WHERE users.id_group IN ' + add + ' AND distribution.level=' + str(i) + ' GROUP BY categories.id_category ORDER BY categories.id_category ASC;')
            amounts = [x[0] for x in cursor.fetchall()]
            for j in range(len(amounts)):
                distributions[j].append(0 if amounts[j] == None else amounts[j])

        cursor.execute('SELECT badges.description, COUNT(*) FROM badges_users JOIN users ON users.id_user=badges_users.email JOIN badges ON badges.id_badge=badges_users.id_badge WHERE users.id_group IN ' + add + ' GROUP BY badges.id_badge ORDER BY badges.id_badge ASC;')
        badges = cursor.fetchall()

        cursor.execute('SELECT categories.category, (SELECT ROUND(AVG(quiz_attempts.score_obtained), 2) FROM quiz_attempts JOIN users ON users.id_user=quiz_attempts.email WHERE quiz_attempts.category=categories.id_category AND users.id_group IN ' + add + ') AS mean, COUNT(*) AS total FROM quiz_attempts JOIN categories ON categories.id_category=quiz_attempts.category JOIN users ON users.id_user=quiz_attempts.email WHERE users.id_group IN ' + add + ' GROUP BY categories.id_category ORDER BY categories.id_category ASC;')
        quiz_attempts = cursor.fetchall()
        general_data = [0] * 6

        sql = 'SELECT COUNT(*) FROM users WHERE id_group IN ' + add + ';'
        cursor.execute(sql)
        general_data[0] = cursor.fetchone()[0]

        general_data[1] = sum([x[1] for x in submissions_by_verdict])
        general_data[2] = sum([x[1] for x in badges])
        general_data[3] = sum([x[1] for x in distributions])

        cursor.execute('SELECT COUNT(*) FROM feedback JOIN users ON users.id_user=feedback.email WHERE users.id_group IN ' + add + ';')
        general_data[4] = cursor.fetchone()[0]

        general_data[5] = sum([x[2] for x in quiz_attempts])

        return render_template('groups.html', page_title=page_title, groups=groups, general_data=general_data, submissions_quantity_summary=submissions_quantity_summary, submissions_by_verdict=submissions_by_verdict, badges=badges, distributions=distributions, quiz_attempts=quiz_attempts)

@app.route('/api/badges_earned', methods=['POST'])
def badges_earned():
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM badges')
        badges = cursor.fetchall()
        cursor.execute('SELECT id_badge FROM badges_users WHERE email=%(email)s AND viewed=True;', { 'email': session['user'] })
        user_badges = [x[0] for x in cursor.fetchall()]
        badges_not_earned = []
        for badge in badges:
            if badge[0] not in user_badges:
                badges_not_earned.append(badge)
        queries = {
            1: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\';', 1],
            2: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\';', 5],
            3: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\';', 10],
            4: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\';', 15],
            5: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\';', 20],
            6: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\' AND verdict_id=3;', 1],
            7: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\' AND verdict_id=3;', 5],
            8: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\' AND verdict_id=3;', 10],
            9: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\' AND verdict_id=3;', 15],
            10: ['SELECT COUNT(*) FROM submission_2 WHERE email=\'USER_EMAIL\' AND verdict_id=3;', 20],
            11: ['SELECT COUNT(DISTINCT(submission_2.id_problem)) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE submission_2.email=\'USER_EMAIL\' AND problems.category=1 AND submission_2.verdict_id=3;', 4],
            12: ['SELECT COUNT(DISTINCT(submission_2.id_problem)) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE submission_2.email=\'USER_EMAIL\' AND problems.category=2 AND submission_2.verdict_id=3;', 4],
            13: ['SELECT COUNT(DISTINCT(submission_2.id_problem)) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE submission_2.email=\'USER_EMAIL\' AND problems.category=3 AND submission_2.verdict_id=3;', 4],
            14: ['SELECT COUNT(DISTINCT(submission_2.id_problem)) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE submission_2.email=\'USER_EMAIL\' AND problems.category=4 AND submission_2.verdict_id=3;', 4],
            15: ['SELECT COUNT(DISTINCT(submission_2.id_problem)) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE submission_2.email=\'USER_EMAIL\' AND problems.category=5 AND submission_2.verdict_id=3;', 4],
            16: ['SELECT COUNT(*) FROM users WHERE id_user=\'USER_EMAIL\' AND id_group != 0;', 1],
            17: ['SELECT COUNT(*) FROM feedback WHERE email=\'USER_EMAIL\';', 1],
            18: ['SELECT COUNT(*) FROM feedback WHERE email=\'USER_EMAIL\';', 5],
            19: ['SELECT COUNT(*) FROM feedback WHERE email=\'USER_EMAIL\';', 10],
            20: ['SELECT COUNT(*) FROM feedback WHERE email=\'USER_EMAIL\';', 15],
            21: ['SELECT COUNT(*) FROM feedback WHERE email=\'USER_EMAIL\';', 20]
        }
        new_badges = {}
        new_badges['badges'] = []
        for x in badges_not_earned:
            if x[0] in queries:
                query = queries[x[0]][0].replace('USER_EMAIL', session['user'])
                cursor.execute(query)
                result_from_query = cursor.fetchone()[0]
                result_from_dicc = queries[x[0]][1]
                if result_from_query == result_from_dicc:
                    new_badges['badges'].append(x)
                    insert_stmt = 'INSERT INTO badges_users (email, id_badge, datetime, viewed) VALUES (%s, %s, %s, %s)'
                    data = (session['user'], x[0], datetime.now(), True)
                    cursor.execute(insert_stmt, data)
                    conn.commit()
        return { 'badges': new_badges['badges'] }, 200
    else:
        return { 'message': 'no_ok' }, 400

@app.route('/api/update_group', methods=['POST'])
def update_group():
    body = request.get_json()
    if body is None:
        return 'The request body is null', 400
    if 'group' not in body:
        return 'You need to specify the group', 400
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET id_group=%(group)s WHERE id_user=%(user)s', { 'group': body['group'], 'user': session['user'] })
        conn.commit()
        return { 'message': 'ok' }, 200
    else:
        return { 'message': 'no_ok' }, 400

@app.route('/api/get_problem', methods=['POST'])
def get_problem():
    body = request.get_json()
    if body is None:
        return 'The request body is null', 400
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    if 'user' in session:
        if session['role'] == 'instructor':
            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute('SELECT id_problem, title, statement, category, level FROM problems WHERE id_problem=%(id_pro)s', { 'id_pro': body['id_problem'] })
            data = [x for x in cursor.fetchone()]
            data[3] = categories[data[3] - 1][1] if data[3] > 0 else 'Sin Categoría'
            cursor.execute('SELECT level FROM feedback WHERE id_problem=%(id_pro)s AND email=%(email)s;', { 'id_pro': body['id_problem'], 'email': session['user'] })
            selected_level = cursor.fetchone()
            data.append(selected_level[0] if selected_level != None else 0)
            cursor.execute('SELECT text, input_description, output_description, observations FROM subproblems WHERE id_problem=%(id_pro)s AND subproblem=1;', { 'id_pro': body['id_problem'] })
            data += [x for x in cursor.fetchone()]
            print(data)
            return { 'problem': data }, 200
        else:
            return { 'message': 'no_ok' }, 400
    else:
        return { 'message': 'no_ok' }, 400

@app.route('/api/update_level_problem_by_instructor', methods=['POST'])
def update_level_problem_by_instructor():
    body = request.get_json()
    if body is None:
        return 'The request body is null', 400
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    if 'id_level' not in body:
        return 'You need to specify the id_level', 400
    if 'user' in session:
        if session['role'] == 'instructor':
            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute('SELECT level FROM feedback WHERE id_problem=%(id_pro)s AND email=%(email)s;', { 'id_pro': body['id_problem'], 'email': session['user'] })
            selected_level = cursor.fetchone()
            if selected_level == None:
                insert_stmt = 'INSERT INTO feedback (id_problem, email, level, status, datetime) VALUES (%s, %s, %s, %s, %s)'
                data = (body['id_problem'], session['user'], body['id_level'], True, datetime.now())
                cursor.execute(insert_stmt, data)
                conn.commit()
            else:
                cursor.execute('UPDATE feedback SET level=%(lvl)s WHERE id_problem=%(id_pro)s AND email=%(email)s', { 'lvl': body['id_level'], 'id_pro': body['id_problem'], 'email': session['user'] })
                conn.commit()
            return { 'message': 'ok' }, 200
        else:
            return { 'message': 'no_ok' }, 400
    else:
        return { 'message': 'no_ok' }, 400

@app.route('/api/submit', methods=['POST'])
def submit():
    body = request.get_json()

    if body is None:
        return 'The request body is null', 400
    
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    
    if 'source_code' not in body:
        return 'You need to specify the source_code', 400

    if 'only_samples' not in body:
        return 'You need to specify the only_samples', 400

    id_problem = body['id_problem']
    source_code = body['source_code']
    only_samples = body['only_samples']
    source_code_to_judge = source_code

    conn = mysql.connect()
    cursor = conn.cursor()

    cursor.execute('SELECT category FROM problems WHERE id_problem=%(id_pro)s;', { 'id_pro': id_problem })
    category_index = cursor.fetchone()

    cursor.execute('SELECT id_problem_1, id_problem_2, id_problem_3, id_problem_4 FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution DESC LIMIT 1;', { 'email': session['user'], 'cat': category_index })

    if int(id_problem) not in cursor.fetchone():
        return 'This problem does not belong to your current problem distribution', 400

    cursor.execute('SELECT additional_code_below FROM subproblems WHERE id_problem=%(id_pro)s AND subproblem=1', { 'id_pro': id_problem })
    additional_code_below = cursor.fetchone()[0]

    if len(additional_code_below) > 0:
        source_code_to_judge += '\n\n' + additional_code_below

    if only_samples:
        cursor.execute('SELECT id_test_case, stdin, expected_output, feedback, sample FROM test_cases WHERE id_problem=%(id_pro)s AND subproblem=1 AND sample=1 ORDER BY sample DESC, id_problem ASC;', { 'id_pro': id_problem})
    else:
        cursor.execute('SELECT id_test_case, stdin, expected_output, feedback, sample FROM test_cases WHERE id_problem=%(id_pro)s AND subproblem=1 ORDER BY sample DESC, id_problem ASC;', { 'id_pro': id_problem})
    
    tests_cases = cursor.fetchall()
    data = { "submissions": [] }
    additional_data = []

    for i in range(len(tests_cases)):
        _, stdin, expected_output, feedback, sample = tests_cases[i]
        payload = {
            "language_id": 71,
            "source_code": source_code_to_judge,
            "stdin": stdin,
            "expected_output": expected_output
        }
        data["submissions"].append(payload)
        additional_data.append([feedback, bool(sample)])

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.90 Safari/537.36'}
        response = requests.post(url_judge0 + '/submissions/batch', json=data, headers=headers, timeout=10)
        tokens = response.json()
        tokens_str = ''
        
        for i in range(len(tokens)):
            tokens_str += tokens[i]['token']
            tokens_str += ',' if i < len(tokens) - 1 else ''
        
        fields = 'stdin,stdout,stderr,status,status_id,token,expected_output'
        timeout = 20
        timeout_start = time.time()

        while time.time() < timeout_start + timeout:
            response = requests.get(url_judge0 + '/submissions/batch?tokens=' + tokens_str + '&base64_encoded=true&fields=' + fields)
            data = response.json()['submissions']
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
        list_verdicts = []

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
            list_verdicts.append(x['status_id'])
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

        if not only_samples:
            cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE id_problem=%(id_pro)s AND email=%(email)s AND score=100 AND valid=True;', { 'id_pro': id_problem, 'email': session['user'] })
            problem_solved = cursor.fetchone()[0]

            tokens = ','.join(list_tokens)
            insert_stmt = 'INSERT INTO submission_2 (id_problem, email, source_code, score, datetime, tokens, valid, verdict_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
            data = (id_problem, session['user'], source_code, percentage_correct, datetime.now(), tokens, True, max(list_verdicts))
            cursor.execute(insert_stmt, data)
            conn.commit()

            if problem_solved == 0:
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
                    
                    id_problem_1, id_problem_2, id_problem_3, id_problem_4 = ids_list

                    insert_stmt = 'INSERT INTO distribution (email, category, level, id_problem_1, id_problem_2, id_problem_3, id_problem_4, datetime) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
                    data = (session['user'], category_index, new_level, id_problem_1, id_problem_2, id_problem_3, id_problem_4, datetime.now())
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
            'give_feedback': give_feedback,
            'only_samples': only_samples
        }

        for item in dicc['submissions']:
            item['stdin'] = modified_b64decode(item['stdin'])
            item['expected_output'] = modified_b64decode(item['expected_output'])
            item['stdout'] = modified_b64decode(item['stdout'])
            item['stderr'] = modified_b64decode(item['stderr'])

        return dicc, 200
    except Exception as e:
        print(repr(e))
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

@app.route('/api/submissions/<int:id_submission>', methods=['GET'])
def get_submission(id_submission=None):
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT email, id_problem, source_code, tokens FROM submission_2 WHERE id_submission=%(id_pro)s;', { 'id_pro': id_submission})
        data = cursor.fetchone()
        dicc = {}
        if data != None:
            email, id_problem, source_code, tokens_str = data
            cursor.execute('SELECT feedback, sample FROM test_cases WHERE id_problem=%(id_pro)s AND subproblem=1 ORDER BY sample DESC, id_problem ASC;', { 'id_pro': id_problem})
            test_cases = [t for t in cursor.fetchall()]
            if email == session['user']:
                dicc['source_code'] = source_code
                dicc['test_cases'] = []
                fields = 'stdin,stdout,stderr,status,expected_output'
                response = requests.get(url_judge0 + '/submissions/batch?tokens=' + tokens_str + '&base64_encoded=true&fields=' + fields)
                data = response.json()['submissions']
                i = 0
                for submission in data:
                    test = {}
                    if test_cases[i][1] == 1:
                        test['stdin'] = modified_b64decode(submission['stdin'])
                        test['expected_output'] = modified_b64decode(submission['expected_output'])
                        test['stdout'] = modified_b64decode(submission['stdout'])
                    
                    test['stderr'] = modified_b64decode(submission['stderr'])
                    test['status_id'] = submission['status']['id']
                    test['status_description'] = submission['status']['description']
                    test['feedback'], test['sample'] = test_cases[i]
                    dicc['test_cases'].append(test)
                    i += 1
                return dicc, 200
            else:
                return { 'message': 'You do not have authorization' }, 400
        else:
            return { 'message': 'ID does not exist' }, 400
    else:
        return { 'message': 'The user is not logged in' }, 400

@app.route('/api/user_progress', methods=['POST'])
def user_progress():
    body = request.get_json()
    if body is None:
        return 'The request body is null', 400
    if 'id_category' not in body:
        return 'You need to specify the category', 400
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        id_category = body['id_category']
        cursor.execute('SELECT level, datetime FROM distribution WHERE email=%(email)s AND category=%(cat)s ORDER BY id_distribution ASC LIMIT 100;', { 'email': session['user'], 'cat': id_category })
        data = cursor.fetchall()
        print(data)
        distribution_ids = [x[0] for x in data]
        dates = [x[1].strftime('%d-%m-%Y') for x in data]

        dicc = {}
        dicc['details'] = {
            'distribution_ids': distribution_ids,
            'dates': dates
        }
        return dicc, 200
    else:
        return { 'message': 'no_ok' }, 400

@app.route('/api/update_category', methods=['POST'])
def update_category():
    body = request.get_json()
    if body is None:
        return 'The request body is null', 400
    if 'id_problem' not in body:
        return 'You need to specify the id_problem', 400
    if 'id_category' not in body:
        return 'You need to specify the id_category', 400
    if 'user' in session:
        if session['role'] == 'instructor':
            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.execute('UPDATE problems SET category=%(cat)s WHERE id_problem=%(id_pro)s', { 'id_pro': body['id_problem'], 'cat': body['id_category'] })
            conn.commit()
            return { 'message': 'ok' }, 200
        else:
            return { 'message': 'no_ok' }, 400
    else:
       return { 'message': 'no_ok' }, 400

@app.route('/api/check_user_for_survey', methods=['GET'])
def check_user_for_survey():
    if 'user' in session:
        conn = mysql.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM survey_answers WHERE email=%(email)s', { 'email': session['user'] });
        survey_answered = True if cursor.fetchone()[0] > 0 else False
        if not survey_answered:
            min_submissions = 3
            min_distributions = 4
            cursor.execute('SELECT COUNT(*) FROM submission_2 WHERE email=%(email)s;', { 'email': session['user'] })
            total_submissions = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM distribution WHERE email=%(email)s;', { 'email': session['user'] })
            total_distributions = cursor.fetchone()[0]
            flag = total_submissions >= min_submissions or total_distributions >= min_distributions
            if flag:
                return { 'message': 'ok' }, 200
            else:
                return { 'message': 'no_ok' }, 200
        else:
            return { 'message': 'no_ok' }, 200
    else:
        return { 'message': 'no_ok' }, 200

@app.route('/submissions', methods=['GET'])
@app.route('/submissions/<int:page>', methods=['GET'])
def submissions(page=None):
    if 'user' not in session:
        return render_template('not_authorized.html', page_title='Acceso denegado')

    page_title = 'Envíos'
    submissions = []
    logged_in = False    
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE email=%(email)s ORDER BY id_submission DESC;', { 'email': session['user'] })
    submissions_length = cursor.fetchone()[0]
    submissions_per_page = 100
    offset = 0
    max_pages = int(submissions_length / submissions_per_page) + 1

    if page != None:
        if page >= 1 and page <= max_pages:
            offset = submissions_per_page * (page - 1)
        else:
            return redirect(url_for('submissions'))

    cursor.execute('SELECT submission_2.id_submission, problems.title, submission_2.score, submission_2.datetime FROM submission_2 JOIN problems ON problems.id_problem=submission_2.id_problem WHERE email=%(email)s ORDER BY id_submission DESC LIMIT %(lim)s OFFSET %(off)s;', { 'email': session['user'], 'lim': submissions_per_page, 'off': offset })
    submissions = cursor.fetchall()
    logged_in = True
    current_page = 1 if page == None else page
    return render_template('submissions.html', page_title=page_title, submissions=submissions, logged_in=logged_in, current_page=current_page, max_pages=max_pages)

@app.route('/launch', methods=['POST'])
@lti(request='initial', role='any', app=app)
def launch(lti=lti):
    conn = mysql.connect()
    cursor = conn.cursor()
    user = request.form.get('lis_person_contact_email_primary')
    name = request.form.get('lis_person_name_given')
    surname = request.form.get('lis_person_name_family')
    cursor.execute('SELECT COUNT(*) FROM users WHERE id_user=%(user)s', { 'user': user })
    if cursor.fetchone()[0] == 0:
        insert_stmt = 'INSERT INTO users (id_user, name, surname, id_group, created_at, active) VALUES (%s, %s, %s, %s, %s, %s)'
        data = (user, name, surname, 0, datetime.now(), True)
        cursor.execute(insert_stmt, data)
        conn.commit()
    else:
        cursor.execute('UPDATE users SET active=True WHERE id_user=%(user)s', { 'user': user })
        conn.commit()
    session['user'] = user
    session['role'] = 'instructor' if 'Instructor' in request.form.get('roles').split(',') else 'learner'
    return redirect(url_for('index'))

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

def scheduled_task():
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT id_problem, AVG(level) FROM feedback WHERE status=1 GROUP BY id_problem;')
    for id_problem, avg in cursor.fetchall():
        new_level = int(round(avg))
        cursor.execute('UPDATE problems SET level=%(lvl)s WHERE id_problem=%(id_pro)s;', { 'lvl': new_level, 'id_pro': id_problem })
        conn.commit()
    cursor.execute('UPDATE feedback SET status=0 WHERE status=1')
    conn.commit()

'''
scheduler.add_job(id='Scheduled Task', func=scheduled_task, trigger='interval', seconds=3600)
scheduler.start()
'''

'''
@app.errorhandler(Exception)
def exception_handler(error):
    return repr(error)
'''

if __name__ == "__main__":
    app.run(host='0.0.0.0')