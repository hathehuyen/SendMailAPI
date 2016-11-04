from flask import jsonify, request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import mysql.connector as mariadb
from datetime import datetime
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
            mariadb_connection = mariadb.connect(host='128.199.136.222', user='maillog', password='maillog',
                                                 database='maillog')
            cursor = mariadb_connection.cursor()
            time = datetime.now()
            sent = True
            cursor.execute("INSERT INTO maillog (time, content, sent) VALUES (%s, %s, %s)", (time, msgtext, sent))
            mariadb_connection.commit()
            mariadb_connection.disconnect()
            return jsonify(result=True)
    except Exception as exc:
        print(exc)
        print 'Send mail error'
        print request.values
        msgtext = request.values['msg']
        mariadb_connection = mariadb.connect(host='128.199.136.222', user='maillog', password='maillog',
                                             database='maillog')
        cursor = mariadb_connection.cursor()
        time = datetime.now()
        sent = False
        cursor.execute("INSERT INTO maillog (time, content, sent) VALUES (%s, %s, %s)", (time, msgtext, sent))
        mariadb_connection.commit()
        mariadb_connection.disconnect()
        return jsonify(result=False)

