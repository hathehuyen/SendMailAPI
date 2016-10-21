import json
from flask import jsonify, request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sendapi import app


@app.route('/send', methods=['POST'], endpoint='send')
def sendmail():
    try:
        if request.method == 'POST':
            msg = MIMEMultipart()
            msg['Subject'] = 'Our family reunion'
            me = app.config['FROM']
            family = app.config['RCPT_TO']
            msg['From'] = me
            msg['To'] = family
            msg.preamble = 'Our family reunion'
            s = smtplib.SMTP('localhost')
            s.sendmail(me, family, msg.as_string())
            s.quit()
            if True:
                return jsonify(result=True, adminId=1)
            else:
                return jsonify(result=False)
    except Exception as exc:
        print(exc)
        print 'Send mail error'
        print request.values
        return jsonify(result=False)

