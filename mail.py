from flask_mail import Mail, Message

mail = Mail()

def send_email(subject, recipients, body):
    msg = Message(subject, recipients=recipients, body=body)
    mail.send(msg) 