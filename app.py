from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Sample in-memory data store
trading_data = []

# API Endpoint to get trading data
@app.route('/api/trades', methods=['GET'])
def get_trades():
    return jsonify(trading_data)

# API Endpoint to add new trading data
@app.route('/api/trades', methods=['POST'])
def add_trade():
    trade = request.json
    trading_data.append(trade)
    return jsonify(trade), 201

# Dashboard route
@app.route('/')
def dashboard():
    return render_template('dashboard.html', trades=trading_data)

# Starting the Flask application
if __name__ == '__main__':
    app.run(debug=True)