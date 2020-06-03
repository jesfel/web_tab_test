from flask import *
import pymongo
from flask_table import Table, Col

class ItemTable(Table):
    name = Col('name', column_html_attrs={'class': 'th-sm'})
    email = Col('email', column_html_attrs={'class': 'th-sm'})
    password = Col('password', column_html_attrs={'class': 'th-sm'})

def search_token(zoho_id, dictionary):
    dict_values = list(dictionary.values())
    param = list(filter(lambda dict_values: dict_values['item_id'] == zoho_id, dict_values))
    token = list(dictionary.keys())[list(dict_values).index(param[0])]
    return [token, dictionary[token]['qt']]

def index():
    return render_template('index.html')

def t_test():
    db_client = pymongo.MongoClient('mongodb://localhost:27017')
    db = db_client['mongologin']
    users = db['users']

    items = list(users.find())#.sort(field_sort,-1))

    table = ItemTable(items, classes=['table table-hover table-responsive-md sortable'], table_id='selectedColumn')

    return render_template('test.html', tables=[table])

def close_van_miami():
    return render_template('vans.html')
