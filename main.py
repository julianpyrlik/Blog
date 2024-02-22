from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column, Session
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

#  TODO: Configure Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    """Takes the user_id as input and returns the user as object"""
    return User.query.get(int(user_id))

# TODO: Create a User table for all your registered users.
# CREATE DATABASE
class Base(DeclarativeBase):
    pass

# Configure the SQLAlchemy database URI
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

    # Relationship
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # Foreign
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    # Relationship
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String(250), nullable=False)

    # Foreign
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"))

    # Relationship
    comment_author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")



with app.app_context():
    db.create_all()

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id == 1:
            return f(*args, **kwargs)
        else:
            abort(code=403)

    return decorated_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit(): # POST
        name = form.name.data
        email = form.email.data
        password = form.password.data
    # hash the password
        hashed_password = generate_password_hash(password=password, method="pbkdf2", salt_length=8)
    # add data to db
    #     check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # flash and render register
            flash(message="Email already exists", category="error")
            return render_template("register.html", form=form, logged_in=current_user.is_authenticated)
        else:
            with app.app_context():
                new_user = User(name=name, email=email, password=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('get_all_posts'))

    else:
        return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():  # POST
        email = form.email.data
        password = form.password.data

        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user and check_password_hash(pwhash=user.password, password=password):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        elif not user:
            flash(message="User doesn't exist", category="error")
            return render_template("login.html", form=form, logged_in=current_user.is_authenticated)
        else:
            flash(message="Wrong password", category="error")
            return render_template("login.html", form=form, logged_in=current_user.is_authenticated)
    else:  # GET
        return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html",
                           all_posts=posts,
                           logged_in=current_user.is_authenticated,
                           user_id=current_user.id if current_user.is_authenticated else None,
                           username=current_user.name if current_user.is_authenticated else None)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit(): # POST
        # If user is logged in, post comment
        if current_user.is_authenticated:
            # add comment to db
            with app.app_context():
                new_comment = Comment(text=form.comment.data,
                                      author_id=current_user.id,
                                      post_id=post_id)
                db.session.add(new_comment)
                db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to login to comment")
            return redirect(url_for("login"))
    else:  # GET
        all_comments = db.session.execute(db.select(Comment)).scalars().all()
        all_authors = db.session.execute(db.select(User)).scalars().all()
        return render_template("post.html",
                               post=requested_post,
                               logged_in=current_user.is_authenticated,
                               user_id=current_user.id if current_user.is_authenticated else None,
                               form=form,
                               current_post=requested_post)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        # author = current_user.name
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():  # POST
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    else:  # GET
        return render_template("make-post.html", form=edit_form, is_edit=True, logged_in=current_user.is_authenticated)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html",
                           logged_in=current_user.is_authenticated,
                           username=current_user.name if current_user.is_authenticated else None)


@app.route("/contact")
def contact():
    return render_template("contact.html",
                           logged_in=current_user.is_authenticated,
                           username=current_user.name if current_user.is_authenticated else None)




if __name__ == "__main__":
    app.run(debug=False, port=5002)
