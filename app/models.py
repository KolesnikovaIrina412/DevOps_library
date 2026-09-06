from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ------------------ Библиотека ------------------
book_genre = db.Table('book_genre',
                      db.Column('book_id', db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
                      db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete='CASCADE'),
                                primary_key=True)
                      )


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Cover(db.Model):
    __tablename__ = 'covers'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(32), nullable=False, unique=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    book = db.relationship('Book', back_populates='cover', foreign_keys=[book_id])


class Branch(db.Model):
    """Модель филиала библиотеки"""
    __tablename__ = 'branches'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    address = db.Column(db.String(300), nullable=False)
    phone = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)


class BookCopy(db.Model):
    """Модель экземпляра книги в конкретном филиале"""
    __tablename__ = 'book_copies'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id', ondelete='CASCADE'), nullable=False)
    inventory_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default='available')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Связи
    book = db.relationship('Book', back_populates='copies', foreign_keys=[book_id])
    branch = db.relationship('Branch', back_populates='copies', foreign_keys=[branch_id])
    loans = db.relationship('BookLoan', back_populates='copy', cascade='all, delete-orphan')


class BookLoan(db.Model):
    """Модель выдачи книги"""
    __tablename__ = 'book_loans'
    id = db.Column(db.Integer, primary_key=True)
    copy_id = db.Column(db.Integer, db.ForeignKey('book_copies.id', ondelete='CASCADE'), nullable=False)
    reader_name = db.Column(db.String(200), nullable=False)
    reader_phone = db.Column(db.String(50))
    loan_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    return_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    copy = db.relationship('BookCopy', back_populates='loans', foreign_keys=[copy_id])


class Book(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    publisher = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # Связи
    genres = db.relationship('Genre', secondary=book_genre, lazy='subquery',
                             backref=db.backref('books', lazy=True))
    cover = db.relationship('Cover', back_populates='book', uselist=False,
                            cascade='all, delete-orphan', foreign_keys=[Cover.book_id])
    copies = db.relationship('BookCopy', back_populates='book',
                             cascade='all, delete-orphan', foreign_keys=[BookCopy.book_id])

    def get_branch_stats(self, branch_id):
        """Получить статистику по книге в конкретном филиале"""
        copies = BookCopy.query.filter_by(book_id=self.id, branch_id=branch_id).all()
        total = len(copies)
        available = sum(1 for c in copies if c.status == 'available')
        issued = sum(1 for c in copies if c.status == 'issued')

        # Подсчет популярности (сколько раз выдавалась)
        popularity = BookLoan.query.join(BookCopy).filter(
            BookCopy.book_id == self.id,
            BookCopy.branch_id == branch_id
        ).count()

        return {
            'total': total,
            'available': available,
            'issued': issued,
            'popularity': popularity
        }

    def get_all_branches_stats(self):
        """Получить статистику по всем филиалам"""
        branches = Branch.query.all()
        stats = {}
        for branch in branches:
            stats[branch] = self.get_branch_stats(branch.id)
        return stats


# Добавляем обратные связи для Branch
Branch.copies = db.relationship('BookCopy', back_populates='branch',
                                cascade='all, delete-orphan', foreign_keys=[BookCopy.branch_id])