'''
Created on Oct 21, 2016

@author: HuyenHa
'''

from flask import Flask
import config

app = Flask(__name__)
app.config.from_object(config.DefaultConfig)


@app.route('/', methods=['GET'])
def index():
    return 'Send Mail API'


import api

