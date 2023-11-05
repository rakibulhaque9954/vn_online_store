from flask_wtf.csrf import CSRFProtect
from flask import Flask, render_template, url_for, request, redirect, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import timedelta, datetime

import os
import smtplib

# Initializing Flask app
app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = 'sdfsdfsdfsdfsd'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

"""Connect to db"""
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shopsite.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

"""Configure Products Table"""
class Products(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False, unique=True)
    image = db.Column(db.String(250), nullable=False)
    category = db.Column(db.String(250), nullable=False)
    price = db.Column(db.Float(250), nullable=False)
    size = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=False)

    cart_items = db.relationship('CartItem', back_populates='product')

    def __repr__(self):
        return self.title


"""Configure Cart Table for management during session"""
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('CartItem', back_populates='cart', cascade="all, delete-orphan")

"""Configure Cart Items Table"""
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Products', back_populates='cart_items')

#
# """Configure Size Table"""
# class Size(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     size = db.Column(db.String(50), nullable=False)
#     product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
#     product = db.relationship('Products', back_populates='sizes')


# Creating a new product
# new_product = Products(
#     title="Tshirt 3",
#     image="path/to/tshirt.jpg",
#     category="tshirts",
#     price=20.0,
#     size='l',
#     description="A very stylish t-shirt."
# )

# Adding the new product and sizes to the session and committing them to the database
with app.app_context():
    # db.session.add(new_product)
    # db.session.commit()
    db.create_all()






@app.route('/')
def home():
    """Home page"""
    all_products = Products.query.all()
    categories = ['posters', 'tshirts', 'aliens']
    product_cats = {}

    for category in categories:
        products = Products.query.filter_by(category=category).all()
        for product in products:
            product_cats.setdefault(category, []).append(product)
    print(product_cats)

    return render_template('index.html', products=all_products)

@app.route('/products/product<index>', methods=['GET', 'POST'])
def product(index):
    """Each Product Display"""
    result = Products.query.get(index)
    category = result.category

    # Fetch other products in the same category
    related_products = Products.query.filter_by(category=category).all()

    return render_template('all_products.html', item=result, related_products=related_products)



# For Display different category of products
@app.route('/categories/products', methods=['GET'])
def categories():
    category = request.args.get('category')
    print(category)
    if category != 'all_products':
        products_in_category = Products.query.filter_by(category=category).all()
        category_name = category.title()
        print(products_in_category)
    else:
        products_in_category = Products.query.all()
        category_name = 'All Products'
        print(products_in_category)

    return render_template('category.html', products=products_in_category, category_name=category_name)

# About Page
@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    # Ensure a cart exists
    if 'cart_id' not in session:
        new_cart = Cart()
        db.session.add(new_cart)
        db.session.commit()
        session['cart_id'] = new_cart.id

    # Add or update the cart item
    cart_id = session['cart_id']
    cart_item = CartItem.query.filter_by(cart_id=cart_id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        new_cart_item = CartItem(cart_id=cart_id, product_id=product_id)
        db.session.add(new_cart_item)

    db.session.commit()
    flash('Product added to cart.')
    redirect_to = request.args.get('next', 'home')
    if redirect_to == 'product':
        return redirect(url_for(redirect_to, index=product_id))
    elif redirect_to == 'categories':
        # print('R', redirect_to)
        category = request.args.get('category')
        # print('c', category)
        return redirect(url_for('categories', category=category))
    return redirect(url_for(redirect_to))

@app.route('/cart', methods=['GET'])
def view_cart():
    total_price = 0.0
    cart_id = session.get('cart_id')
    if cart_id:
        cart_items = CartItem.query.filter_by(cart_id=cart_id).all()
        for item in cart_items:
            total_price += item.quantity * item.product.price
        print(total_price)
    else:
        cart_items = []
    return render_template('cart.html', cart_items=cart_items, total_price=round(total_price, 2))

@app.route('/remove_from_cart/<int:cart_item_id>')
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.get(cart_item_id)
    if cart_item:
        if cart_item.quantity > 1:
            # If the quantity is greater than 1, decrement it by 1
            cart_item.quantity -= 1
        else:
            # If the quantity is 1 or less, remove the item from the cart
            db.session.delete(cart_item)
        db.session.commit()
        flash('Item removed from cart.')
    else:
        flash('Item not found in cart.')
    redirect_to = request.args.get('next', 'home')
    return redirect(url_for(redirect_to))


@app.route('/checkout')
def checkout():
    total_price = 0.0
    cart_id = session.get('cart_id')
    if cart_id:
        cart_items = CartItem.query.filter_by(cart_id=cart_id).all()
        for item in cart_items:
            total_price += item.quantity * item.product.price
        print(total_price)
    else:
        cart_items = []
    return render_template('checkout.html', cart_items=cart_items, total_price=round(total_price, 2))

@app.route('/order_placed', methods=['POST'])
def process_order():
    total_price = 0.0
    cart_id = session.get('cart_id')
    if cart_id:
        cart_items = CartItem.query.filter_by(cart_id=cart_id).all()
        for item in cart_items:
            total_price += item.quantity * item.product.price

        # Collect customer information (you may need to update these fields)
        if request.method == 'POST':
            print(request.form)
            full_name = request.form['full_Name']
            print(full_name)
            email = request.form.get('email')
            address = request.form.get('address')

            # Create the email message with order details
            email_body = f"""
            Xin chào,

            Một đơn hàng mới đã được đặt tại cửa hàng của bạn. Dưới đây là chi tiết đơn hàng:

            Tên khách hàng: {full_name}

            Email: {email}

            Địa chỉ giao hàng: {address}

            Sản phẩm đã đặt hàng:
            """
            for item in cart_items:
                email_body += f"- {item.product.title} (Số lượng: {item.quantity}, Giá: ${'{:0.2f}'.format(item.product.price)})\n"

            email_body += f"**Tổng cộng: ${'{:0.2f}'.format(total_price)}**\n"

            # Send the email notification to the owner using SMTP
            send_email_notification(email_body)

            # Render the receipt template (for the buyer) in Vietnamese
            return render_template('receipt.html', cart_items=cart_items, total_price=round(total_price, 2))

    else:
        cart_items = []

        # Render the receipt template (for the buyer) in Vietnamese
        return render_template('receipt.html', cart_items=cart_items, total_price=0.0)

def send_email_notification(email_body):
    try:
        # Configure SMTP settings
        smtp_server = 'smtp.gmail.com'  # Replace with your SMTP server
        smtp_port = 587  # Replace with your SMTP port
        smtp_username = 'smtp@gmail.com'  # Replace with your SMTP username
        smtp_password = 'smtp_password'  # Replace with your SMTP password

        # Create an SMTP connection
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Start TLS encryption
        server.login(smtp_username, smtp_password)

        # Email sender and recipient
        sender_email = 'example@gmail.com'  # Replace with your email address
        recipient_email = 'owner@gmail.com'  # Replace with the owner's email address

        # Create the email message
        subject = 'New Order Notification'  # Subject of the email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach the email body
        msg.attach(MIMEText(email_body, 'plain'))

        # Send the email
        server.sendmail(sender_email, recipient_email, msg.as_string())

        # Close the SMTP server
        server.quit()
    except Exception as e:
        flash(f"Error sending email notification: {str(e)}")

@app.context_processor
def context_processor():
    print("Context processor called")  # This line is for debugging purposes
    cart_id = session.get('cart_id')
    if cart_id:
        # Retrieve all CartItem instances for the cart
        cart_items = CartItem.query.filter_by(cart_id=cart_id).all()
        # Sum the quantities of all CartItems
        total_quantity = sum(item.quantity for item in cart_items)
    else:
        total_quantity = 0

    return {'total_quantity': total_quantity}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
