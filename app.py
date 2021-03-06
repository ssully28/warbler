import os

from flask import Flask, render_template, request, flash, redirect, session, g, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from forms import UserAddForm, LoginForm, MessageForm, UserEditForm, DirectMessageForm
from models import db, connect_db, User, Message, Like, DirectMessage

from decorators import auth_check
from autocompletetrie import AutoCompleteTrie


CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgres:///yak'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")

toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        # was except IntegrityError as e:
        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""
    do_logout()
    return redirect('/')


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    # snagging messages in order from the database;
    # user.messages won't be in order by default
    messages = (Message
                .query
                .filter(Message.user_id == user_id)
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())
    return render_template('users/show.html', user=user, messages=messages)


@app.route('/users/<int:user_id>/following')
@auth_check
def show_following(user_id):
    """Show list of people this user is following."""

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
@auth_check
def users_followers(user_id):
    """Show list of followers of this user."""

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
@auth_check
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    followee = User.query.get_or_404(follow_id)
    g.user.following.append(followee)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
@auth_check
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    followee = User.query.get(follow_id)
    g.user.following.remove(followee)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
@auth_check
def profile():
    """Update profile for current user."""

    form = UserEditForm(obj=g.user)

    if form.validate_on_submit():

        form_password = form.password.data
        user = User.authenticate(g.user.username, form_password)
        if user:
            user.username = form.username.data
            user.email = form.email.data
            user.image_url = form.image_url.data
            user.header_image_url = form.header_image_url.data
            user.bio = form.bio.data

            db.session.commit()
            flash("Profile updated.", 'success')
            return redirect(f'/users/{user.id}')
        else:
            flash("Invalid credentials.", 'danger')
            return redirect('/')

    return render_template("users/edit.html", form=form)


@app.route('/users/delete', methods=["POST"])
@auth_check
def delete_user():
    """Delete user."""

    do_logout()
    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
@auth_check
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    form = MessageForm()

    if form.validate_on_submit():
        
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        # Now handling via ajax so no need to redirect:
        # return redirect(f"/users/{g.user.id}")
        return jsonify({"status": "success"})

    # Now handling via ajax so not rendering
    # return render_template('messages/new.html', form=form)
    return jsonify({"form": form.serialize()})


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
@auth_check
def messages_destroy(message_id):
    """Delete a message."""

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


##############################################################################
# Like Feature:


@app.route('/messages/<int:message_id>/like', methods=["POST"])
@auth_check
def messages_like(message_id):
    """
    Like a message
    Toggle liking - first check if message is
    already liked by g.user if so delete the like
    if not, then create the like...
    """
    is_liked = Like.query.filter_by(message_id=message_id,
                                    user_id=g.user.id).first()
    
    liked_status = ''
    if is_liked:
        # Remove the like:
        db.session.delete(is_liked)
        db.session.commit()
        liked_status = 'unliked'
    else:
        # Create the like:
        like = Like(user_id=g.user.id, message_id=message_id)
        db.session.add(like)
        db.session.commit()
        liked_status = 'liked'


    # Go back to the page that we liked/unliked the message from!
    # Changed to asyc js so comment out redirect:
    #return redirect(request.referrer)

    return jsonify({"status": liked_status})


@app.route('/users/<int:user_id>/likes')
@auth_check
def show_likes(user_id):
    """
    Show Likes - when clicking the number of
    likes on the user page show all messages
    that user has liked.
    """
    likes = Like.query.filter_by(user_id=g.user.id).all()
    message_ids = [like.message_id for like in likes]
    messages = Message.query.filter(Message.id.in_(message_ids)).all()

    # Basic SQL of what we're looking for here....
    # SELECT * FROM messages 
    # JOIN likes 
    # ON likes.message_id = messages.id 
    # WHERE likes.user_id = g.user.id

    return render_template("/messages/show_likes.html", messages=messages)

##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followees
    """

    if g.user:
        # Grab user ids for all that user is following:
        target_ids = [user.id for user in g.user.following]

        # Add users id to that list:
        target_ids.append(g.user.id)
        messages = (Message
                    .query
                    .order_by(Message.timestamp.desc())
                    .filter(Message.user_id.in_(target_ids))
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages)

    else:
        return render_template('home-anon.html')


##############################################################################
# autocomplete

@app.route('/autocomplete')
def autocomplete():
    
    subword = request.args['subword']
    # Grab a list of names. 
    list_names = [name for (name,) in db.session.query(User.username)]

    # Build the autocomplete trie based of the list names
    ac_trie = AutoCompleteTrie()
    ac_trie.add_words_to_trie(list_names)
    autocomplete = ac_trie.autocomplete(subword)
    return jsonify({'autocomplete': autocomplete })


##############################################################################
# direct messages

@app.route('/directmessage/new', methods=["POST", "GET"])
@auth_check
def direct_message():
    """
    Send a Direct Message:
    Show form if GET. If valid, update message and redirect to user page.
    """

    form = DirectMessageForm()

    if form.validate_on_submit():
        # Create the DirectMessage Object:

        # The user id is actually coming into this 
        # as the username value (aka "Kings" instead of 123)
        # so we need to convert that from username to the
        # id

        user_found = User.query.filter_by(username=form.to_user.data).first()
        
        if user_found:
            
            direct_message = DirectMessage(from_id=g.user.id,
                                           to_id=user_found.id, 
                                           text=form.text.data)

            # Insert object into the database:
            db.session.add(direct_message)

            # commit - duh.
            db.session.commit()

            return jsonify({"status": "success"})
        else:
            
            form.errors['user_error'] = "User does not exist"

    return jsonify({"form": form.serialize()})


@app.route('/directmessage/list')
@auth_check
def direct_message_list():
    """Return a list of Direct Messages User Has Received"""

    msg_list = [dm.serialize() for dm in g.user.inbox]

    return jsonify(msg_list)


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req
