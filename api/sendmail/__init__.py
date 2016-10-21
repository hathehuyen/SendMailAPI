import json
from werkzeug.utils import secure_filename
from career_api.proxy import Session,admin_service, license_obj, company_obj,company_user_obj,license_service
from career_api.proxy import admin_session, work_exp_obj, certificate_obj, edu_hist_obj, document_obj
from career_api.proxy import assignment_obj,user_obj, license_category_obj, admin_obj
from flask import jsonify, request
import base64
from career_api import app
import os
import datetime

@app.route('/sendmail/account/login', methods=['POST'], endpoint='sendmail-account-login')
def login():
    try:
        login = request.values['login']
        password = request.values['password']
        role = request.values['role'] if 'role' in request.values else False
        if not role:
            token = Session.start(login, password, 'sendmail')
            if token:
                return jsonify(result=True, token=token, role='sendmail')
            if not token:
                token = Session.start(login, password, 'cc')
                if token:
                    return jsonify(result=True, token=token, role='cc')
        if role:
            token = Session.start(login, password, role)
            return jsonify(result=True, token=token, role=role)
        raise Exception('Invalid account %s or password %s' % (login, password))
    except Exception as exc:
        print(exc)
        print 'Admin login error '
        print request.values
        return jsonify(result=False)


@app.route('/sendmail/account', methods=['GET', 'PUT', 'POST'], endpoint='sendmail-account')
@admin_session
def account(session):
    try:
        if request.method == 'GET':
            adminList = admin_obj.getAdmins()
            return jsonify(result=True, adminList=adminList)
        if request.method == 'PUT':
            admin = json.loads(request.values['sendmail'])
            admin_obj.updateAdmin(admin['login'], admin['password'], request.values['role'])
            return jsonify(result=True)
        if request.method == 'POST':
            admin = json.loads(request.values['sendmail'])
            adminId = admin_obj.createAdmin(admin['login'], admin['password'], request.values['role'])
            if adminId:
                return jsonify(result=True, adminId=adminId)
            else:
                return jsonify(result=False)
    except Exception as exc:
        print(exc)
        print 'Admin account error '
        print request.values
        return jsonify(result=False)

