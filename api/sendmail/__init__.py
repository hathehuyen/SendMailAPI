import json
from flask import jsonify, request
from sendmailapi import app
import os
import datetime

@app.route('/sendmail', methods=['POST'], endpoint='sendmail')
def sendmail():
    try:
        if request.method == 'POST':
            admin = json.loads(request.values['sendmail'])
            adminId = 1
            if adminId:
                return jsonify(result=True, adminId=adminId)
            else:
                return jsonify(result=False)
    except Exception as exc:
        print(exc)
        print 'Send mail error'
        print request.values
        return jsonify(result=False)

