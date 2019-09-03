import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def connect(mail_addr, password):
    server = smtplib.SMTP('smtp.gmail.com', 25)
    server.ehlo()
    server.starttls()
    server.login(mail_addr, password)
    return server

def send_mail(fromaddr, password, toaddr, body, subject="Sentinel Notification", dev=False):
    if dev:
        print("[Dev mode] Aborting to send an email to {0}: {1}\n".format(toaddr, body))
        return
    server = connect(fromaddr, password)
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = subject
    msg_body = "<html> <body> "+ body + "</body></html>"
    msg.attach(MIMEText(body, 'html'))
    msg = msg.as_string()
    try:
        server.sendmail(fromaddr, toaddr, msg)
    except Exception as e:
        print(str(datetime.now()),str(e))
    try:
        server.quit()
    except:
        pass
