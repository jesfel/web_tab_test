from run import app as application

if __name__ == '__main__':
    app.secret_key = 'mysecret'
    app.config['SESSION_TYPE'] = 'filesystem'
    application.run()
