from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
import jwt
import datetime
from app_settings import env, current_env

from flask_cors import cross_origin
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity 
import os
import sys
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# Get the database configuration for the current environment from app_settings.py
db_config = env[current_env]['db_config']

app.config['MYSQL_HOST'] = db_config['host']
app.config['MYSQL_PORT'] = db_config['port']
app.config['MYSQL_USER'] = db_config['user']
app.config['MYSQL_PASSWORD'] = db_config['password']
app.config['MYSQL_DB'] = db_config['database']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'  

mysql = MySQL(app)

app.config['JWT_SECRET_KEY'] = 'work-india-testing'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 1800

jwt_manager = JWTManager(app)

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data['username']
    password = data['password']
    email = data['email']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
                (username, password, email))
    mysql.connection.commit()
    cur.close()

    return jsonify({'status': 'Account successfully created'}), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()

    if user and user['password'] == password:
        user_id = user['id']
        token = jwt.encode({'username': username, 'exp': datetime.utcnow() + timedelta(hours=1)}, app.config['JWT_SECRET_KEY'])
        return jsonify({'status': 'Login successful','user_id': user_id, 'access_token': token}), 200
    else:
        return jsonify({'status': 'Incorrect username/password provided. Please retry'}), 401

@app.route('/api/trains/create', methods=['POST'])
def create_train():
    data = request.get_json()
    train_name = data['train_name']
    source = data['source']
    destination = data['destination']
    seat_capacity = data['seat_capacity']
    arrival_time_at_source = data.get('arrival_time_at_source', None)
    arrival_time_at_destination = data.get('arrival_time_at_destination', None)

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO trains (train_name, source, destination, seat_capacity, arrival_time_at_source, arrival_time_at_destination) VALUES (%s, %s, %s, %s, %s, %s)",
                (train_name, source, destination, seat_capacity, arrival_time_at_source, arrival_time_at_destination))
    mysql.connection.commit()

    # Get the auto-generated train ID
    train_id = cur.lastrowid

    cur.close()

    return jsonify({'message': 'Train added successfully', 'train_id': train_id}), 200


@app.route('/api/trains/availability', methods=['GET'])
def get_seat_availability():
    source = request.args.get('source')
    destination = request.args.get('destination')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM trains WHERE source = %s AND destination = %s", (source, destination))
    trains = cur.fetchall()
    cur.close()

    availability_data = []

    for train in trains:
        train_id = train['id']
        train_name = train['train_name']

        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) as booked_seats FROM bookings WHERE train_id = %s", (train_id,))
        booked_seats = cur.fetchone()['booked_seats']
        cur.close()

        available_seats = train['seat_capacity'] - booked_seats

        availability_data.append({
            'train_id': train_id,
            'train_name': train_name,
            'available_seats': available_seats
        })

    return jsonify(availability_data), 200

@app.route('/api/trains/<int:train_id>/book', methods=['POST'])
def book_seat(train_id):
    data = request.get_json()
    user_id = data['user_id']
    no_of_seats = data['no_of_seats']

    # Check seat availability
    cur = mysql.connection.cursor()
    cur.execute("SELECT seat_capacity FROM trains WHERE id = %s", (train_id,))
    seat_capacity = cur.fetchone()['seat_capacity']
    cur.execute("SELECT COUNT(*) as booked_seats FROM bookings WHERE train_id = %s", (train_id,))
    booked_seats = cur.fetchone()['booked_seats']
    cur.close()

    available_seats = seat_capacity - booked_seats

    if available_seats < no_of_seats:
        return jsonify({'message': 'Not enough available seats'}), 400

    # Book the seats
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO bookings (train_id, user_id, no_of_seats) VALUES (%s, %s, %s)",
                (train_id, user_id, no_of_seats))
    mysql.connection.commit()

    # Get the auto-generated booking ID
    booking_id = cur.lastrowid

    cur.close()

    return jsonify({'message': 'Seat(s) booked successfully', 'booking_id': booking_id}), 200



@app.route('/api/bookings/<int:booking_id>', methods=['GET'])
def get_booking_details(booking_id):
    # Check if the booking belongs to the authenticated user (based on user_id)
    auth_token = request.headers.get('Authorization')
    if not auth_token:
        return jsonify({'message': 'Authorization token is missing'}), 401

    try:
        decoded_token = jwt.decode(auth_token.split(' ')[1], app.config['SECRET_KEY'])
        auth_user_id = decoded_token['username']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.DecodeError:
        return jsonify({'message': 'Invalid token'}), 401

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
    booking = cur.fetchone()
    cur.close()

    if not booking:
        return jsonify({'message': 'Booking not found'}), 404

    if auth_user_id != booking['user_id']:
        return jsonify({'message': 'Unauthorized to access this booking'}), 403

    # Fetch train details for the booking
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM trains WHERE id = %s", (booking['train_id'],))
    train = cur.fetchone()
    cur.close()

    booking_details = {
        'booking_id': booking_id,
        'train_id': train['id'],
        'train_name': train['train_name'],
        'user_id': booking['user_id'],
        'no_of_seats': booking['no_of_seats'],
        'arrival_time_at_source': train['arrival_time_at_source'],
        'arrival_time_at_destination': train['arrival_time_at_destination']
    }

    return jsonify(booking_details), 200


if __name__ == '__main__':
    app.run(debug=True)