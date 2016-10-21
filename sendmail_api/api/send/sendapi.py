from flask import jsonify, request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sendmail_api import app


@app.route('/send', methods=['POST'], endpoint='send')
def sendmail():
    try:
        if request.method == 'POST':
            msg = MIMEMultipart('alternative')
            msg['Subject'] = app.config['SUBJECT']
            me = app.config['FROM']
            family = app.config['RCPT_TO']
            msg['From'] = app.config['FROM']
            msg['To'] = family
            msgtext = request.values['msg']
            txtpart = MIMEText(msgtext, 'plain')
            msg.attach(txtpart)
            s = smtplib.SMTP('localhost')
            s.sendmail(me, family.split(","), msg.as_string())
            s.quit()
            return jsonify(result=True)
    except Exception as exc:
        print(exc)
        print 'Send mail error'
        print request.values
        return jsonify(result=False)

