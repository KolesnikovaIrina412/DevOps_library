from flask import render_template, request, redirect, url_for, flash, Blueprint
from models import db, Book, Genre, Cover, Branch
import hashlib
import bleach
from markdown import markdown
import os
from PIL import Image
from io import BytesIO

books_bp = Blueprint('books', __name__)


ALLOWED_TAGS = ['p', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote', 'img']


def sanitize_html(text):
    return bleach.clean(text, tags=ALLOWED_TAGS, strip=True)


def markdown_to_html(text):
    safe_text = sanitize_html(text)
    return markdown(safe_text, extensions=['fenced_code', 'tables'])


def compute_md5(file_data):
    return hashlib.md5(file_data).hexdigest()


# Главная страница со списком книг + поиск
@books_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Получаем фильтры из GET-параметров
    search_title = request.args.get('title', '').strip()
    search_author = request.args.get('author', '').strip()
    search_genres = request.args.getlist('genres')
    search_years = request.args.getlist('years')
    pages_from = request.args.get('pages_from', '', type=int)
    pages_to = request.args.get('pages_to', '', type=int)

    query = Book.query

    # Применяем фильтры
    if search_title:
        query = query.filter(Book.title.ilike(f'%{search_title}%'))
    if search_author:
        query = query.filter(Book.author.ilike(f'%{search_author}%'))
    if search_genres:
        query = query.filter(Book.genres.any(Genre.id.in_(search_genres)))
    if search_years:
        query = query.filter(Book.year.in_(search_years))

    # Сортировка: сначала новые
    query = query.order_by(Book.year.desc(), Book.id.desc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Для фильтров: все года из БД
    all_years = db.session.query(Book.year).distinct().order_by(Book.year.desc()).all()
    all_years = [y[0] for y in all_years if y[0]]

    all_genres = Genre.query.order_by(Genre.name).all()

    return render_template('books_list.html',
                           books=pagination.items,
                           pagination=pagination,
                           search_title=search_title,
                           search_author=search_author,
                           search_genres=search_genres,
                           search_years=search_years,
                           pages_from=pages_from,
                           pages_to=pages_to,
                           all_genres=all_genres,
                           all_years=all_years)


# Просмотр книги
@books_bp.route('/book/<int:book_id>')
def view(book_id):
    book = Book.query.get_or_404(book_id)

    # Конвертируем Markdown в HTML
    book.description_html = markdown_to_html(book.description)

    return render_template('book_view.html', book=book)



# Добавление книги
@books_bp.route('/book/create', methods=['GET', 'POST'])
def create():
    genres = Genre.query.order_by(Genre.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        year = request.form.get('year', type=int)
        publisher = request.form.get('publisher', '').strip()
        author = request.form.get('author', '').strip()
        selected_genres = request.form.getlist('genres')
        cover_file = request.files.get('cover')

        errors = {}

        # Валидация
        if not title:
            errors['title'] = 'Название обязательно'
        if not description:
            errors['description'] = 'Описание обязательно'
        if not year or year < 0 or year > 2026:
            errors['year'] = 'Укажите корректный год (0-2026)'
        if not publisher:
            errors['publisher'] = 'Издательство обязательно'
        if not author:
            errors['author'] = 'Автор обязателен'
        if not cover_file or cover_file.filename == '':
            errors['cover'] = 'Обложка обязательна'

        if errors:
            return render_template('book_form.html',
                                   title='Добавить книгу',
                                   book=None,
                                   genres=genres,
                                   errors=errors,
                                   form_data=request.form), 400

        # Создаём книгу
        book = Book(
            title=title,
            description=sanitize_html(description),
            year=year,
            publisher=publisher,
            author=author
        )
        db.session.add(book)
        db.session.flush()  # Получаем book.id

        # Добавляем жанры
        for gid in selected_genres:
            genre = Genre.query.get(gid)
            if genre:
                book.genres.append(genre)

        # Сохраняем обложку
        img_data = cover_file.read()
        md5_hash = compute_md5(img_data)

        # Проверяем, есть ли уже такая обложка
        existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()

        if existing_cover:
            # Используем существующее изображение
            cover = Cover(
                filename=existing_cover.filename,
                mime_type=existing_cover.mime_type,
                md5_hash=md5_hash,
                book_id=book.id
            )
            db.session.add(cover)
        else:
            # Сохраняем новое изображение
            ext = cover_file.filename.rsplit('.', 1)[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                flash('Неподдерживаемый формат изображения', 'danger')
                db.session.rollback()
                return redirect(url_for('books.create'))

            new_filename = f"cover_{book.id}.{ext}"
            save_path = os.path.join('static', 'images', new_filename)

            # Создаём директорию, если её нет
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Оптимизируем изображение
            img = Image.open(BytesIO(img_data))
            img.thumbnail((500, 500))
            img.save(save_path, optimize=True, quality=85)

            cover = Cover(
                filename=new_filename,
                mime_type=cover_file.mimetype,
                md5_hash=md5_hash,
                book_id=book.id
            )
            db.session.add(cover)

        db.session.commit()
        flash(f'Книга "{book.title}" успешно добавлена', 'success')
        return redirect(url_for('books.view', book_id=book.id))

    return render_template('book_form.html',
                           title='Добавить книгу',
                           book=None,
                           genres=genres,
                           errors={},
                           form_data={})


# Редактирование книги
@books_bp.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
def edit(book_id):
    book = Book.query.get_or_404(book_id)

    genres = Genre.query.order_by(Genre.name).all()

    if request.method == 'POST':
        book.title = request.form.get('title', '').strip()
        book.description = sanitize_html(request.form.get('description', '').strip())
        book.year = request.form.get('year', type=int)
        book.publisher = request.form.get('publisher', '').strip()
        book.author = request.form.get('author', '').strip()
        selected_genres = request.form.getlist('genres')

        errors = {}

        if not book.title:
            errors['title'] = 'Название обязательно'
        if not book.description:
            errors['description'] = 'Описание обязательно'
        if not book.year or book.year < 0 or book.year > 2026:
            errors['year'] = 'Укажите корректный год'
        if not book.publisher:
            errors['publisher'] = 'Издательство обязательно'
        if not book.author:
            errors['author'] = 'Автор обязателен'

        if errors:
            return render_template('book_form.html',
                                   title='Редактировать книгу',
                                   book=book,
                                   genres=genres,
                                   errors=errors,
                                   form_data=request.form), 400

        # Обновляем жанры
        book.genres.clear()
        for gid in selected_genres:
            genre = Genre.query.get(gid)
            if genre:
                book.genres.append(genre)

        db.session.commit()
        flash(f'Книга "{book.title}" успешно обновлена', 'success')
        return redirect(url_for('books.view', book_id=book.id))

    # Подготовка данных для формы
    form_data = {
        'title': book.title,
        'description': book.description,
        'year': book.year,
        'publisher': book.publisher,
        'author': book.author,
        'genres': [str(g.id) for g in book.genres]
    }

    return render_template('book_form.html',
                           title='Редактировать книгу',
                           book=book,
                           genres=genres,
                           errors={},
                           form_data=form_data)


# Удаление книги (только admin)
@books_bp.route('/book/<int:book_id>/delete', methods=['POST'])
def delete(book_id):
    book = Book.query.get_or_404(book_id)
    title = book.title

    # Удаляем файл обложки, если он существует
    if book.cover:
        cover_path = os.path.join('static', 'images', book.cover.filename)
        if os.path.exists(cover_path):
            try:
                os.remove(cover_path)
            except:
                pass  # Не критично, если не удалится

    db.session.delete(book)
    db.session.commit()

    flash(f'Книга "{title}" успешно удалена', 'success')
    return redirect(url_for('books.index'))


# Добавьте этот маршрут в конец файла books.py

@books_bp.route('/book/<int:book_id>/branches')
def branches(book_id):
    book = Book.query.get_or_404(book_id)
    branches = Branch.query.order_by(Branch.name).all()

    # Собираем статистику по каждому филиалу
    branches_stats = []
    for branch in branches:
        stats = book.get_branch_stats(branch.id)
        branches_stats.append({
            'branch': branch,
            'stats': stats
        })

    return render_template('book_branches.html',
                           book=book,
                           branches_stats=branches_stats)


# Добавьте этот маршрут для инициализации тестовых филиалов
@books_bp.route('/init-branches')
def init_branches():
    if Branch.query.first():
        flash('Филиалы уже существуют', 'info')
        return redirect(url_for('books.index'))

    branches = [
        ('Центральная библиотека', 'ул. Ленина, 1', '+7 (123) 456-78-90'),
        ('Филиал №1', 'ул. Гагарина, 15', '+7 (123) 456-78-91'),
        ('Филиал №2', 'пр. Победы, 78', '+7 (123) 456-78-92'),
        ('Детская библиотека', 'ул. Пушкина, 10', '+7 (123) 456-78-93'),
    ]

    for name, address, phone in branches:
        branch = Branch(name=name, address=address, phone=phone)
        db.session.add(branch)

    db.session.commit()
    flash('Тестовые филиалы добавлены', 'success')
    return redirect(url_for('books.index'))