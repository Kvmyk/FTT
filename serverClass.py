from flask import Flask, jsonify, request, send_file

class Server():

    def __init__(self):
        self.data = None
    def get_data(self):
        return self.data
    def set_data(self, data):
        self.data = data

app = Flask(__name__)

@app.route('/my-first-api', methods=['GET'])

def hello():

    name = request.args.get('name')

    if name is None:
        text = 'Hello!'

    else:
        text = 'Hello ' + name + '!'

    return jsonify({"message": text})

if __name__ == '__main__':
    app.run(debug=True, port=8000)