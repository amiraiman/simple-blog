from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    login_required,
    current_user,
    logout_user,
)
from forms import CreatePostForm, RegisterUserForm, LoginUserForm, CreateCommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

# App config
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "some_secret_here")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URI", "sqlite:///blog.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Extensions
db = SQLAlchemy(app)
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app)
login_manager = LoginManager()
login_manager.init_app(app)


#  Table Schema
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = relationship("User", back_populates="blog_post")
    comment = relationship("Comment", back_populates="post")


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=True, unique=True)
    name = db.Column(db.String(250), nullable=True)
    password = db.Column(db.String(250), nullable=True)
    blog_post = relationship("BlogPost", back_populates="user")
    comment = relationship("Comment", back_populates="user")


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = relationship("User", back_populates="comment")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    post = relationship("BlogPost", back_populates="comment")


# Get user for session callback
@login_manager.user_loader
def load_user(id):
    return User.query.get(id)


# Decorators
def admin_only(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated and current_user.id == 1:
            return fn(*args, **kwargs)
        return abort(403)

    return wrapper


@app.route("/")
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("get_all_posts"))

    form = RegisterUserForm()
    if form.validate_on_submit():
        already_exists = User.query.filter_by(email=form.email.data).first()
        if already_exists:
            flash("That email already exists. Please log in instead.")
            return redirect(url_for("login"))

        new_user = User(
            name=form.name.data,
            password=generate_password_hash(form.password.data),
            email=form.email.data,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("get_all_posts"))

    form = LoginUserForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("Account does not exist. Please double check your credentials.")
    return render_template("login.html", form=form)


@login_required
@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CreateCommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login before commenting")
            return redirect(url_for("login"))
        new_comment = Comment(
            comment=comment_form.comment.data, post_id=post_id, user_id=current_user.id
        )
        db.session.add(new_comment)
        db.session.commit()
    all_comments = Comment.query.filter_by(post_id=post_id).all()
    return render_template(
        "post.html", post=requested_post, form=comment_form, comments=all_comments
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            user_id=current_user.id,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
