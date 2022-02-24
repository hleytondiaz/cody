from flask import Flask
from flask import render_template
from flask import request
from flaskext.markdown import Markdown
from flaskext.mysql import MySQL

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
    ('programas-secuenciales', 'Programas Secuenciales'),
    ('condicionales', 'Condicionales'),
    ('ciclos', 'Ciclos'),
    ('Strings', 'strings'),
    ('funciones', 'Funciones'),
    ('listas', 'Listas'),
    ('tuplas', 'Tuplas'),
    ('diccionarios', 'Diccionarios')
]

def check_quiz_attempted(email, category):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM quiz_attempts WHERE email = %(email)s AND category = %(cat)s;', { 'email': email, 'cat': category})
    total_attempts = cursor.fetchone()[0]
    return total_attempts > 0

def get_category_index(categories, category):
    for i in range(len(categories)):
        if categories[i][0] == category:
            return i + 1

@app.route('/')
def index():
    return render_template('index.html', progress_list=categories)

@app.route('/quizzes/<string:category>', methods=['GET', 'POST'])
def quiz(category=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    category_index = get_category_index(categories, category)
    category_not_formatted, quiz_category = categories[category_index - 1]
    questions = []
    quiz_done = False

    if request.method == 'GET':
        if check_quiz_attempted(email, category_index):
            quiz_done = True
        else:
            cursor.execute('(SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 1 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 2 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 3 ORDER BY RAND() LIMIT 3);', { 'cat': 1 })
            quiz = cursor.fetchall()
            for i in range(len(quiz)):
                id_quiz_question, question = quiz[i]
                cursor.execute('SELECT id_alternative, description FROM quiz_alternatives WHERE id_question = %(id)s ORDER BY RAND();', { 'id': id_quiz_question })
                alternatives = cursor.fetchall()
                questions.append([i + 1, id_quiz_question, question, alternatives])

    if request.method == 'POST':
        if check_quiz_attempted(email, category_index):
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
            if total_score < 0.33:
                final_level = 'BÁSICO'
            elif total_score < 0.66:
                final_level = 'MEDIO'
            else:
                final_level = 'AVANZADO'
            final_percentage = round(cont * 100 / 9)
            '''
                INSERT HERE
            '''
            return render_template('quiz_done.html', final_level=final_level, final_percentage=final_percentage, quiz_category=quiz_category, category_not_formatted=category_not_formatted)
    return render_template('quiz.html', questions=questions, quiz_category=quiz_category, quiz_done=quiz_done)

@app.route('/exercises/<string:category>')
@app.route('/exercises/<string:category>/<int:id_exercise>')
def exercises(category=None, id_exercise=None):
    if category and id_exercise:
        return render_template('exercise.html', )
    else:
        exercises = [
            'Ejemplo 1',
            'Ejemplo 2',
            'Ejemplo 3',
            'Ejemplo 4'
        ]
        return render_template('exercises.html', exercises=exercises)