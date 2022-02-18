from flask import Flask
from flask import render_template

app = Flask(__name__)

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
    questions = [
        'Ejemplo 1',
        'Ejemplo 2',
        'Ejemplo 3',
        'Ejemplo 4',
        'Ejemplo 5'
    ]
    quiz_category = 'Programas Básicos'
    return render_template('quiz.html', questions=questions, quiz_category=quiz_category)

@app.route('/exercises/<string:category>')
def exercises(category=None):
    return render_template('exercises.html')