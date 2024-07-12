import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Firestore database
db = firestore.client()

def send_email(to_email, subject, body):
    from_email = os.getenv("EMAIL_USER")
    from_password = os.getenv("EMAIL_PASSWORD")
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, from_password)
    text = msg.as_string()
    server.sendmail(from_email, to_email, text)
    server.quit()

def confirm_user_registration():
    username = input("Enter the Username of the user to confirm registration: ")
    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("User not found.")
        return

    user_data = user.to_dict()
    if not user_data.get('email_verified', False):
        auth.update_user(user_data['uid'], email_verified=True)
        user_ref.update({'email_verified': True})
        print("User registration confirmed successfully.")
    else:
        print("User registration already confirmed.")

def modify_user_balance():
    username = input("Enter the Username of the user: ")
    new_balance = float(input("Enter the new balance: "))
    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("User not found.")
        return

    user_ref.update({'balance': new_balance})
    print("User balance updated successfully.")

def send_bulk_emails():
    subject = input("Enter the email subject: ")
    body = input("Enter the email body: ")

    users = db.collection('users').get()
    for user in users:
        user_data = user.to_dict()
        send_email(user_data['email'], subject, body)

    print("Bulk emails sent successfully.")

def delete_user_account():
    username = input("Enter the Username of the user: ")
    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("User not found.")
        return

    user_data = user.to_dict()
    auth.delete_user(user_data['uid'])
    user_ref.delete()
    print("User account deleted successfully.")

def revert_transaction():
    username = input("Enter the Username of the user who initiated the transaction: ")
    transaction_id = input("Enter the Transaction ID to revert: ")

    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("User not found.")
        return

    user_data = user.to_dict()
    transactions = user_data.get('transactions', [])
    transaction = next((t for t in transactions if t['transaction_id'] == transaction_id), None)

    if not transaction:
        print("Transaction not found.")
        return

    if transaction['type'] != 'transfer':
        print("Only transfer transactions can be reverted.")
        return

    sender_ref = db.collection('users').document(transaction['sender'])
    receiver_ref = db.collection('users').document(transaction['receiver'])

    sender_data = sender_ref.get().to_dict()
    receiver_data = receiver_ref.get().to_dict()

    sender_ref.update({'balance': sender_data['balance'] + transaction['amount'] + 10})
    receiver_ref.update({'balance': receiver_data['balance'] - transaction['amount']})

    # Remove the transaction from both users
    sender_transactions = sender_data.get('transactions', [])
    receiver_transactions = receiver_data.get('transactions', [])
    sender_transactions = [t for t in sender_transactions if t['transaction_id'] != transaction_id]
    receiver_transactions = [t for t in receiver_transactions if t['transaction_id'] != transaction_id]
    sender_ref.update({'transactions': sender_transactions})
    receiver_ref.update({'transactions': receiver_transactions})

    # Notify users via email
    send_email(sender_data['email'], 'Transaction Reverted', f"Your transaction {transaction_id} has been reverted.")
    send_email(receiver_data['email'], 'Transaction Reverted', f"Transaction {transaction_id} has been reverted.")

    print("Transaction reverted successfully.")

def admin_menu():
    while True:
        print("\nAdmin Panel")
        print("1. Confirm User Registration")
        print("2. Modify User Balance")
        print("3. Send Bulk Emails")
        print("4. Delete User Account")
        print("5. Revert Transaction")
        print("6. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            confirm_user_registration()
        elif choice == '2':
            modify_user_balance()
        elif choice == '3':
            send_bulk_emails()
        elif choice == '4':
            delete_user_account()
        elif choice == '5':
            revert_transaction()
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    admin_menu()
