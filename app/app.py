from flask import Flask, render_template, redirect, url_for
from models import db
from books import books_bp


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Инициализация БД
db.init_app(app)

# Регистрация blueprint'ов
app.register_blueprint(books_bp)


# Основные маршруты
@app.route('/')
def index():
    return redirect(url_for('books.index'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# Инициализация БД с начальными данными
def init_db():
    with app.app_context():
        db.create_all()

        from models import Genre

        # Добавляем начальные жанры
        if Genre.query.first() is None:
            genres = [
                'Фентази', 'Детектив', 'Повседневность',
                'Научная литература', 'Приключения', 'Триллер',
                'Исторический', 'Фантастика', 'Комедия'
            ]
            for genre_name in genres:
                db.session.add(Genre(name=genre_name))
            db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    app.run(debug=True)
