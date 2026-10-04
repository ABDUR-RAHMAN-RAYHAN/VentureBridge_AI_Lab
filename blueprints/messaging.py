from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from extensions import db
from models import Connection, Message, User
from forms import MessageForm
from utils import log_action

bp = Blueprint("messaging", __name__, url_prefix="/messages")


def _user_connections(user_id):
    return Connection.query.filter(or_(Connection.user_a_id == user_id, Connection.user_b_id == user_id)).all()


@bp.route("/")
@login_required
def inbox():
    connections = _user_connections(current_user.id)
    threads = []
    for c in connections:
        other_id = c.other(current_user.id)
        other = User.query.get(other_id)
        last_msg = Message.query.filter_by(connection_id=c.id).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter_by(connection_id=c.id, receiver_id=current_user.id, read_at=None).count()
        threads.append({"connection": c, "other": other, "last_msg": last_msg, "unread": unread})
    threads.sort(key=lambda t: t["last_msg"].created_at if t["last_msg"] else t["connection"].created_at, reverse=True)
    return render_template("messaging/inbox.html", threads=threads)


@bp.route("/<int:connection_id>", methods=["GET", "POST"])
@login_required
def thread(connection_id):
    connection = Connection.query.get_or_404(connection_id)
    # Server-side enforcement: only participants of this connection may access it
    if current_user.id not in (connection.user_a_id, connection.user_b_id):
        abort(403)
    other_id = connection.other(current_user.id)
    other = User.query.get(other_id)

    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(connection_id=connection.id, sender_id=current_user.id,
                      receiver_id=other_id, body=form.body.data)
        db.session.add(msg)
        db.session.commit()
        log_action("message_sent", f"connection_id={connection.id}")
        return redirect(url_for("messaging.thread", connection_id=connection.id))

    # mark incoming as read
    unread = Message.query.filter_by(connection_id=connection.id, receiver_id=current_user.id, read_at=None).all()
    for m in unread:
        m.read_at = datetime.utcnow()
    db.session.commit()

    msgs = Message.query.filter_by(connection_id=connection.id).order_by(Message.created_at.asc()).all()
    return render_template("messaging/thread.html", connection=connection, other=other, messages=msgs, form=form)
