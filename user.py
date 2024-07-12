import firebase_admin
from firebase_admin import credentials, firestore, auth
import random
import string
import re
from datetime import datetime
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Initialize Firebase Admin SDK
cred = credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Firestore database
db = firestore.client()

# Helper functions
def generate_account_id():
    prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
    suffix = ''.join(random.choices(string.digits, k=8))
    return prefix + suffix

def validate_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True

def send_email(to_email, subject, body):
    from_email = "your_email@gmail.com"
    from_password = "your_email_password"
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

def create_account():
    first_name = input("Enter First Name: ")
    last_name = input("Enter Last Name: ")
    phone_number = input("Enter Phone Number: ")
    email = input("Enter Email: ")
    base_currency = input("Enter Base Currency (Naira, Euro, Pounds, Rupee, Kuwait Dinar, Dollar): ")
    username = input("Enter Username: ")
    password = input("Enter Password: ")

    if not validate_password(password):
        print("Password must be at least 8 characters long and contain both letters and numbers.")
        return

    transaction_pin = input("Enter Transaction PIN: ")
    profile_picture_path = input("Enter path to your profile picture: ")
    
    # Crop the image to 1:1 ratio
    image = Image.open(profile_picture_path)
    width, height = image.size
    new_width = new_height = min(width, height)
    left = (width - new_width)/2
    top = (height - new_height)/2
    right = (width + new_width)/2
    bottom = (height + new_height)/2
    image = image.crop((left, top, right, bottom))
    cropped_image_path = f"cropped_{username}.png"
    image.save(cropped_image_path)

    account_id = generate_account_id()
    balance = 1000  # Initial balance, for example purposes

    # Create user in Firebase Auth
    try:
        user_record = auth.create_user(
            email=email,
            email_verified=False,
            phone_number=phone_number,
            password=password,
            display_name=f"{first_name} {last_name}",
            photo_url=cropped_image_path,
            disabled=False
        )
        print(f'Successfully created new user: {user_record.uid}')
    except firebase_admin.auth.AuthError as e:
        print(f'Error creating user: {e}')
        return

    # Store user data in Firestore
    db.collection('users').document(username).set({
        'first_name': first_name,
        'last_name': last_name,
        'phone_number': phone_number,
        'email': email,
        'base_currency': base_currency,
        'password': password,
        'transaction_pin': transaction_pin,
        'account_id': account_id,
        'balance': balance,
        'profile_picture': cropped_image_path,  # Store path to cropped profile picture
        'uid': user_record.uid,
        'transactions': []
    })
    print(f"Account created successfully! Your account ID is {account_id}")

def generate_transaction_id(sender_first_name, sender_last_name):
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    initials = sender_first_name[0] + sender_last_name[0]
    return f"{now}-{initials}"

def log_transaction(username, transaction):
    user_ref = db.collection('users').document(username)
    user = user_ref.get().to_dict()
    transactions = user.get('transactions', [])
    transactions.append(transaction)
    user_ref.update({'transactions': transactions})

def transfer_money():
    sender_username = input("Enter your Username: ")
    sender_ref = db.collection('users').document(sender_username)
    sender = sender_ref.get()

    if not sender.exists:
        print("Sender account not found.")
        return

    sender_data = sender.to_dict()
    receiver_identifier = input("Enter the receiver's Username or Account ID: ")

    receiver_query = db.collection('users').where('username', '==', receiver_identifier).get() or \
                     db.collection('users').where('account_id', '==', receiver_identifier).get()

    if not receiver_query:
        print("Receiver account not found.")
        return

    receiver_data = receiver_query[0].to_dict()

    print(f"Receiver's Name: {receiver_data['first_name']} {receiver_data['last_name']}")
    print(f"Receiver's Profile Picture: {receiver_data['profile_picture']}")

    confirmation = input("Do you confirm the receiver's information is correct? (yes/no): ")
    if confirmation.lower() != "yes":
        print("Transfer cancelled.")
        return

    amount = float(input("Enter amount to transfer: "))

    if amount + 10 > sender_data["balance"]:
        print("Insufficient funds.")
        return

    # Generate transaction ID
    transaction_id = generate_transaction_id(sender_data['first_name'], sender_data['last_name'])

    # Update balances in Firestore
    sender_ref.update({'balance': sender_data["balance"] - (amount + 10)})
    db.collection('users').document(receiver_query[0].id).update({'balance': receiver_data["balance"] + amount})

    # Log transaction
    transaction = {
        'transaction_id': transaction_id,
        'type': 'transfer',
        'amount': amount,
        'sender': sender_username,
        'receiver': receiver_identifier,
        'timestamp': datetime.now().isoformat()
    }
    log_transaction(sender_username, transaction)
    log_transaction(receiver_identifier, transaction)

    # Send email notifications
    send_email(sender_data['email'], 'Money Sent', f"You have sent {amount} to {receiver_data['first_name']} {receiver_data['last_name']}. Transaction ID: {transaction_id}")
    send_email(receiver_data['email'], 'Money Received', f"You have received {amount} from {sender_data['first_name']} {sender_data['last_name']}. Transaction ID: {transaction_id}")

    print("Transfer successful!")

def view_transaction_history():
    username = input("Enter your Username: ")
    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("Account not found.")
        return

    transactions = user.to_dict().get('transactions', [])
    if not transactions:
        print("No transactions found.")
    else:
        for transaction in transactions:
            print(transaction)

def delete_account():
    username = input("Enter your Username: ")
    user_ref = db.collection('users').document(username)
    user = user_ref.get()

    if not user.exists:
        print("Account not found.")
        return

    password = input("Enter your Password to confirm deletion: ")
    user_data = user.to_dict()

    if user_data["password"] != password:
        print("Incorrect password.")
        return

    # Delete user from Firebase Auth
    try:
        auth.delete_user(user_data["uid"])
        print(f'Successfully deleted user: {user_data["uid"]}')
    except firebase_admin.auth.AuthError as e:
        print(f'Error deleting user: {e}')
        return

    # Delete user data from Firestore
    user_ref.delete()
    print("Account deleted successfully!")

def request_money():
    requester_username = input("Enter your Username: ")
    requester_ref = db.collection('users').document(requester_username)
    requester = requester_ref.get()

    if not requester.exists:
        print("Requester account not found.")
        return

    receiver_identifier = input("Enter the receiver's Username or Account ID: ")
    receiver_query = db.collection('users').where('username', '==', receiver_identifier).get() or \
                     db.collection('users').where('account_id', '==', receiver_identifier).get()

    if not receiver_query:
        print("Receiver account not found.")
        return

    receiver_data = receiver_query[0].to_dict()

    amount = float(input("Enter amount to request (max 10,000): "))
    if amount > 10000:
        print("Cannot request more than 10,000.")
        return

    # Here you can add the functionality to send a request notification to the receiver
    print(f"Request of {amount} {requester.to_dict()['base_currency']} sent to {receiver_data['first_name']} {receiver_data['last_name']}")

def user_registration_login():
    while True:
        print("\nWelcome to the Banking System")
        print("1. Register")
        print("2. Login")
        print("3. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            create_account()
        elif choice == '2':
            username = input("Enter Username: ")
            password = input("Enter Password: ")

            user_ref = db.collection('users').document(username)
            user = user_ref.get()

            if not user.exists or user.to_dict()["password"] != password:
                print("Invalid username or password.")
            else:
                print("Login successful!")
                return username
        elif choice == '3':
            return None
        else:
            print("Invalid choice. Please try again.")

def main():
    user = user_registration_login()
    if user:
        while True:
            print("\nBanking System")
            print("1. Transfer Money")
            print("2. Request Money")
            print("3. Delete Account")
            print("4. View Transaction History")
            print("5. Logout")
            choice = input("Enter your choice: ")

            if choice == '1':
                transfer_money()
            elif choice == '2':
                request_money()
            elif choice == '3':
                delete_account()
            elif choice == '4':
                view_transaction_history()
            elif choice == '5':
                break
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
