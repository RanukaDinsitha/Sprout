from flask import Flask, render_template

# app configuration lines
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# route sprout
@app.route('/')
def home():
    return render_template('index.j2')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
