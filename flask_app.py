import os
import sys
from threading import Thread
from flask import Flask, render_template, session, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail, Message

import requests
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard to guess string'
app.config['SQLALCHEMY_DATABASE_URI'] =\
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['API_KEY'] = os.environ.get('API_KEY')
app.config['API_URL'] = os.environ.get('API_URL')
app.config['API_FROM'] = os.environ.get('API_FROM')

app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')

bootstrap = Bootstrap(app)
moment = Moment(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return '<Role %r>' % self.name


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def __repr__(self):
        return '<User %r>' % self.username

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(128))
    recipient = db.Column(db.String(256)) # Armazena a lista de e-mails como texto
    subject = db.Column(db.String(128))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<EmailLog {self.id}>'

def send_simple_message(to, subject, newUser):

    email_body = f"Novo usuário cadastrado: {newUser}"

    full_subject = app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + ' ' + subject

    print('Enviando mensagem (POST)...', flush=True)
    print('URL: ' + str(app.config['API_URL']), flush=True)
    print('api: ' + str(app.config['API_KEY']), flush=True)
    print('from: ' + str(app.config['API_FROM']), flush=True)
    print('to: ' + str(to), flush=True)
    print('subject: ' + full_subject, flush=True)
    print('text: ' + email_body, flush=True)

    resposta = requests.post(app.config['API_URL'],
                             auth=("api", app.config['API_KEY']),
                             data={"from": app.config['API_FROM'],
                                   "to": to,
                                   "subject": full_subject,
                                   "text": email_body})

    if resposta:
        log_entry = EmailLog(
            sender=app.config['API_FROM'],
            recipient=str(to),
            subject=full_subject,
            body=email_body,
            timestamp=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()


    print('Enviando mensagem (Resposta)...' + str(resposta) + ' - ' + datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), flush=True)
    return resposta


class NameForm(FlaskForm):
    name = StringField('Qual é o seu nome?', validators=[DataRequired()])
    email = BooleanField('Deseja enviar e-mail para flaskaulasweb@zohomail.com?')
    submit = SubmitField('Submit')


@app.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.name.data).first()
        if user is None:

            user_role = Role.query.filter_by(name='User').first()
            if user_role is None:
                user_role = Role(name='User')
                db.session.add(user_role)

            user = User(username=form.name.data, role=user_role)
            db.session.add(user)
            db.session.commit()
            session['known'] = False

            if app.config['FLASKY_ADMIN']:
                destinatarios = [app.config['FLASKY_ADMIN']]
                if form.email.data:
                    destinatarios.append("flaskaulasweb@zohomail.com")
                send_simple_message(destinatarios, 'Novo usuário', form.name.data)
        else:
            session['known'] = True
        session['name'] = form.name.data
        return redirect(url_for('index'))

    users_list = User.query.order_by(User.username).all()

    return render_template('index.html',
                           form=form,
                           name=session.get('name'),
                           known=session.get('known', False),
                           users=users_list)

@app.route('/emailsEnviados')
def emails():
    email_list = EmailLog.query.order_by(EmailLog.timestamp.desc()).all()
    return render_template('emails.html', emails=email_list)