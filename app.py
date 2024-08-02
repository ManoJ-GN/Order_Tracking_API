from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)

def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='shopeasy',
            user='root',
            password='tiger'  
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None

@app.route('/', methods=['POST'])
def webhook():
    data = request.json
    if data:
        awb = data.get('awb')
        courier_name = data.get('courier_name')
        current_status = data.get('current_status')
        current_status_id = data.get('current_status_id')
        shipment_status = data.get('shipment_status')
        shipment_status_id = data.get('shipment_status_id')
        current_timestamp = data.get('current_timestamp')  # Use this field carefully
        order_id = data.get('order_id')
        sr_order_id = data.get('sr_order_id')
        awb_assigned_date_str = data.get('awb_assigned_date')
        pickup_scheduled_date_str = data.get('pickup_scheduled_date')
        etd_str = data.get('etd')
        scans = data.get('scans', [])
        is_return = data.get('is_return')
        channel_id = data.get('channel_id')
        pod_status = data.get('pod_status')
        pod = data.get('pod')
        email = data.get('email')  # Extract email for notification

        # Validate datetime fields
        try:
            if current_timestamp:
                current_timestamp = datetime.strptime(current_timestamp, '%Y-%m-%d %H:%M:%S')
            else:
                raise ValueError("current_timestamp is missing or invalid")
            
            if awb_assigned_date_str:
                awb_assigned_date = datetime.strptime(awb_assigned_date_str, '%Y-%m-%d %H:%M:%S')
            else:
                raise ValueError("awb_assigned_date is missing or invalid")

            if pickup_scheduled_date_str:
                pickup_scheduled_date = datetime.strptime(pickup_scheduled_date_str, '%Y-%m-%d %H:%M:%S')
            else:
                raise ValueError("pickup_scheduled_date is missing or invalid")

            if etd_str:
                etd = datetime.strptime(etd_str, '%Y-%m-%d %H:%M:%S')
            else:
                raise ValueError("etd is missing or invalid")
        except ValueError as e:
            return jsonify({"status": "error", "message": f"Date parsing error: {e}"}), 400

        # Parse scans dates
        parsed_scans = []
        for scan in scans:
            try:
                scan_date = datetime.strptime(scan.get('date'), '%Y-%m-%d %H:%M:%S')
                parsed_scans.append({
                    'date': scan_date,
                    'status': scan.get('status'),
                    'activity': scan.get('activity'),
                    'location': scan.get('location'),
                    'sr-status': scan.get('sr-status'),
                    'sr-status-label': scan.get('sr-status-label')
                })
            except (ValueError, TypeError) as e:
                return jsonify({"status": "error", "message": f"Scan date parsing error: {e}"}), 400

        # Log the data for debugging
        print(f"AWB: {awb}, Courier Name: {courier_name}, Current Status: {current_status}, Current Status ID: {current_status_id}, Shipment Status: {shipment_status}, Shipment Status ID: {shipment_status_id}, Current_Time_stamp: {current_timestamp}, Order ID: {order_id}, SR Order ID: {sr_order_id}, AWB Assigned Date: {awb_assigned_date}, Pickup Scheduled Date: {pickup_scheduled_date}, ETD: {etd}, Scans: {parsed_scans}, Is Return: {is_return}, Channel ID: {channel_id}, POD Status: {pod_status}, POD: {pod}, Email: {email}")

        # Update the order status in the database
        update_order_status({
            'awb': awb,
            'courier_name': courier_name,
            'current_status': current_status,
            'current_status_id': current_status_id,
            'shipment_status': shipment_status,
            'shipment_status_id': shipment_status_id,
            'current_timestamp': current_timestamp,
            'order_id': order_id,
            'sr_order_id': sr_order_id,
            'awb_assigned_date': awb_assigned_date,
            'pickup_scheduled_date': pickup_scheduled_date,
            'etd': etd,
            'is_return': is_return,
            'channel_id': channel_id,
            'pod_status': pod_status,
            'pod': pod,
            'scans': parsed_scans
        })

        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "No data received"}), 400


def update_order_status(data):
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        
        # Update Shipment table
        shipment_query = """
        UPDATE Shipment
        SET 
            courier_name = %s,
            current_status = %s,
            current_status_id = %s,
            shipment_status = %s,
            shipment_status_id = %s,
            current_timestamp = %s,
            sr_order_id = %s,
            awb_assigned_date = %s,
            pickup_scheduled_date = %s,
            etd = %s,
            is_return = %s,
            channel_id = %s,
            pod_status = %s,
            pod = %s
        WHERE
            awb = %s
        """
        shipment_values = (
            data.get('courier_name'),
            data.get('current_status'),
            data.get('current_status_id'),
            data.get('shipment_status'),
            data.get('shipment_status_id'),
            data.get('current_timestamp'),
            data.get('sr_order_id'),
            data.get('awb_assigned_date'),
            data.get('pickup_scheduled_date'),
            data.get('etd'),
            data.get('is_return'),
            data.get('channel_id'),
            data.get('pod_status'),
            data.get('pod'),
            data.get('awb')
        )
        
        try:
            # Execute shipment update
            cursor.execute(shipment_query, shipment_values)
            print(f"Updated Shipment with AWB: {data.get('awb')}")

            # Handle scans
            scans = data.get('scans', [])
            for scan in scans:
                scan_query = """
                UPDATE Scan
                SET 
                    status = %s,
                    activity = %s,
                    location = %s,
                    sr_status = %s,
                    sr_status_label = %s,
                    date = %s
                WHERE
                    awb = %s 
                """
                scan_values = (
                    scan.get('status'),
                    scan.get('activity'),
                    scan.get('location'),
                    scan.get('sr-status'),
                    scan.get('sr-status-label'),
                    scan.get('date'),
                    data.get('awb')
                )
                
                # Execute scan update
                cursor.execute(scan_query, scan_values)
            
            # Commit the changes
            connection.commit()
            print("Changes committed to the database")
        except Error as e:
            print(f"SQL Error: {e}")
        finally:
            cursor.close()
            connection.close()


        # Notify the customer after updating the order status
        # notify_customer(data.get('email'), data.get('current_status'))

def notify_customer(email, status):
    from_address = "sveccha.apps@gmail.com"  # Your email address
    password = "4VhALB7qcgbYn0wv"  # Your email password
    to_address = email
    subject = "Order Status Update"
    body = f"Dear customer, your order status has been updated to '{status}'. Thank you for shopping with us!"

    # Set up the server
    server = smtplib.SMTP(host='smtp-relay.brevo.com', port=587)
    server.starttls()
    server.login(from_address, password)

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Send the email
    server.send_message(msg)
    server.quit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
