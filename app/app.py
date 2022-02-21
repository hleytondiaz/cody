from flask import Flask
from flask import render_template
from flaskext.markdown import Markdown
from flaskext.mysql import MySQL

app = Flask(__name__)
mysql = MySQL()

app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_PORT'] = 3306
app.config['MYSQL_DATABASE_DB'] = 'smoj_database'
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'b1@g24v0o&gNuYhLaamTyEV0y%*Xz7Xg'

mysql.init_app(app)
Markdown(app)

@app.route('/')
def index():
    progress_list = [
        'Programas Básicos',
        'Condicionales',
        'Ciclos',
        'Strings',
        'Funciones',
        'Listas',
        'Tuplas',
        'Diccionarios'
    ]
    return render_template('index.html', progress_list=progress_list)

@app.route('/quizzes/<string:category>')
def quiz(category=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute('(SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 1 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 2 ORDER BY RAND() LIMIT 3) UNION (SELECT id_question, question FROM quiz_questions WHERE category = %(cat)s AND level = 3 ORDER BY RAND() LIMIT 3);', { 'cat': 1 })
    quiz = cursor.fetchall()
    questions = []
    for i in range(len(quiz)):
        id_quiz_question, question = quiz[i]
        cursor.execute('SELECT id_alternative, description FROM quiz_alternatives WHERE id_quiz = %(id)s ORDER BY RAND();', { 'id': id_quiz_question })
        alternatives = cursor.fetchall()
        questions.append([i + 1, id_quiz_question, question, alternatives])
    quiz_category = 'Programas Básicos'
    return render_template('quiz.html', questions=questions, quiz_category=quiz_category)

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