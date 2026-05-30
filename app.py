from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from decimal import Decimal
from datetime import date

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # замените на случайную строку в реальном проекте


DB_PARAMS = {
    "dbname": "auto_parts_shop",
    "user": "postgres",
    "password": "qwerty",   
    "host": "localhost",
    "port": 5432
}

def get_db_connection():
    return psycopg2.connect(**DB_PARAMS)

# Декоратор для проверки ролей
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in allowed_roles:
                flash('Доступ запрещён.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------- Главная страница (каталог) ----------
@app.route('/')
def index():
    return redirect(url_for('catalog'))

# ---------- Регистрация ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        phone = request.form['phone']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO Clients (FullName, Phone, Email, PasswordHash, DeliveryAddress, Role)
                VALUES (%s, %s, %s, %s, %s, 'client')
            """, (fullname, phone, email, password_hash, address))
            conn.commit()
            flash('Регистрация успешна! Теперь войдите.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Пользователь с таким email уже существует.', 'danger')
        finally:
            cur.close()
            conn.close()
    return render_template('register.html')

# ---------- Вход ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT Id, FullName, PasswordHash, Role FROM Clients WHERE Email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_role'] = user[3]
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('catalog'))
        else:
            flash('Неверный email или пароль.', 'danger')
    return render_template('login.html')

# ---------- Выход ----------
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('catalog'))

# ---------- Каталог и поиск ----------
@app.route('/catalog')
def catalog():
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT p.Id, p.Name, p.Price, p.QuantityInStock, c.Name as CategoryName, p.Manufacturer
        FROM Products p
        LEFT JOIN Categories c ON p.CategoryId = c.Id
        WHERE (p.Name ILIKE %s OR p.Manufacturer ILIKE %s)
    """
    params = [f'%{search}%', f'%{search}%']
    if category_id:
        query += " AND p.CategoryId = %s"
        params.append(category_id)
    cur.execute(query, params)
    products = cur.fetchall()
    cur.execute("SELECT Id, Name FROM Categories ORDER BY Name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('catalog.html', products=products, categories=categories,
                           selected_category=category_id, search=search)

# ---------- Карточка товара ----------
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.Id, p.Name, p.Price, p.QuantityInStock, p.Description, p.Manufacturer,
               c.Name as CategoryName, p.Code, p.ImageUrl
        FROM Products p
        LEFT JOIN Categories c ON p.CategoryId = c.Id
        WHERE p.Id = %s
    """, (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    if not product:
        flash('Товар не найден.', 'danger')
        return redirect(url_for('catalog'))
    return render_template('product_detail.html', product=product)

# ---------- Корзина (сессионная) ----------
@app.route('/cart')
def cart():
    cart_items = session.get('cart', {})
    items = []
    total = Decimal('0')
    if cart_items:
        conn = get_db_connection()
        cur = conn.cursor()
        for product_id, qty in cart_items.items():
            cur.execute("SELECT Id, Name, Price, QuantityInStock FROM Products WHERE Id = %s", (product_id,))
            product = cur.fetchone()
            if product:
                price = Decimal(str(product[2]))
                subtotal = price * qty
                items.append({
                    'id': product[0],
                    'name': product[1],
                    'price': price,
                    'quantity': qty,
                    'stock': product[3],
                    'subtotal': subtotal
                })
                total += subtotal
        cur.close()
        conn.close()
    return render_template('cart.html', items=items, total=total)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    cart = session.get('cart', {})
    product_id_str = str(product_id)
    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    session['cart'] = cart
    flash('Товар добавлен в корзину', 'success')
    return redirect(request.referrer or url_for('catalog'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    for key in list(cart.keys()):
        new_qty = request.form.get(f'qty_{key}')
        if new_qty and new_qty.isdigit() and int(new_qty) > 0:
            cart[key] = int(new_qty)
        else:
            cart.pop(key, None)
    session['cart'] = cart
    flash('Корзина обновлена', 'info')
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash('Товар удалён из корзины', 'info')
    return redirect(url_for('cart'))

# ---------- Оформление заказа ----------
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Для оформления заказа войдите в систему', 'warning')
        return redirect(url_for('login'))
    cart_items = session.get('cart', {})
    if not cart_items:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('catalog'))
    if request.method == 'POST':
        delivery_method = request.form['delivery_method']
        payment_method = request.form['payment_method']
        address = request.form.get('address', '')
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Получаем данные из корзины
            items = []
            total = Decimal('0')
            for product_id, qty in cart_items.items():
                cur.execute("SELECT Price, QuantityInStock FROM Products WHERE Id = %s", (product_id,))
                price, stock = cur.fetchone()
                if stock < qty:
                    flash(f'Недостаточно товара на складе', 'danger')
                    return redirect(url_for('cart'))
                price_dec = Decimal(str(price))
                subtotal = price_dec * qty
                items.append((product_id, qty, price_dec))
                total += subtotal
            # Создаём заказ
            cur.execute("""
                INSERT INTO Orders (ClientId, OrderDate, Status, TotalPrice, DeliveryMethod, PaymentMethod)
                VALUES (%s, %s, 'new', %s, %s, %s) RETURNING Id
            """, (session['user_id'], date.today(), total, delivery_method, payment_method))
            order_id = cur.fetchone()[0]
            # Добавляем позиции заказа и списываем товары
            for product_id, qty, price in items:
                cur.execute("""
                    INSERT INTO OrderItems (OrderId, ProductId, Quantity, Price)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, product_id, qty, price))
                cur.execute("UPDATE Products SET QuantityInStock = QuantityInStock - %s WHERE Id = %s", (qty, product_id))
            conn.commit()
            # Очищаем корзину
            session.pop('cart', None)
            flash(f'Заказ №{order_id} оформлен!', 'success')
            return redirect(url_for('orders'))
        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при оформлении заказа: {e}', 'danger')
        finally:
            cur.close()
            conn.close()
    else:
        # GET: показываем форму, подставляем адрес из профиля
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DeliveryAddress FROM Clients WHERE Id = %s", (session['user_id'],))
        address = cur.fetchone()[0] or ''
        cur.close()
        conn.close()
        return render_template('checkout.html', address=address)

# ---------- Просмотр заказов клиента ----------
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.Id, o.OrderDate, o.Status, o.TotalPrice, o.DeliveryMethod, o.PaymentMethod
        FROM Orders o
        WHERE o.ClientId = %s
        ORDER BY o.OrderDate DESC
    """, (session['user_id'],))
    orders_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('orders.html', orders=orders_list)

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    # Проверка принадлежности заказа пользователю или права админа/менеджера
    cur.execute("SELECT ClientId FROM Orders WHERE Id = %s", (order_id,))
    result = cur.fetchone()
    if not result:
        flash('Заказ не найден', 'danger')
        return redirect(url_for('orders'))
    client_id = result[0]
    if client_id != session['user_id'] and session.get('user_role') not in ('admin', 'manager'):
        flash('Нет доступа к этому заказу', 'danger')
        return redirect(url_for('orders'))
    cur.execute("""
        SELECT oi.Quantity, oi.Price, p.Name, p.Code
        FROM OrderItems oi
        JOIN Products p ON oi.ProductId = p.Id
        WHERE oi.OrderId = %s
    """, (order_id,))
    items = cur.fetchall()
    cur.execute("SELECT Status, TotalPrice, DeliveryMethod, PaymentMethod, OrderDate FROM Orders WHERE Id = %s", (order_id,))
    order_info = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('order_detail.html', order_id=order_id, items=items, order_info=order_info)

# ---------- Административная панель (только admin/manager) ----------
@app.route('/admin')
@role_required(['admin', 'manager'])
def admin_panel():
    return render_template('admin/index.html')

# Управление категориями
@app.route('/admin/categories')
@role_required(['admin', 'manager'])
def admin_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT Id, Name, Description FROM Categories ORDER BY Id")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/category/add', methods=['GET', 'POST'])
@role_required(['admin', 'manager'])
def admin_category_add():
    if request.method == 'POST':
        name = request.form['name']
        desc = request.form['description']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO Categories (Name, Description) VALUES (%s, %s)", (name, desc))
        conn.commit()
        cur.close()
        conn.close()
        flash('Категория добавлена', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/category_form.html')

@app.route('/admin/category/edit/<int:id>', methods=['GET', 'POST'])
@role_required(['admin', 'manager'])
def admin_category_edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        desc = request.form['description']
        cur.execute("UPDATE Categories SET Name=%s, Description=%s WHERE Id=%s", (name, desc, id))
        conn.commit()
        flash('Категория обновлена', 'success')
        return redirect(url_for('admin_categories'))
    cur.execute("SELECT Name, Description FROM Categories WHERE Id=%s", (id,))
    cat = cur.fetchone()
    cur.close()
    conn.close()
    if not cat:
        flash('Категория не найдена', 'danger')
        return redirect(url_for('admin_categories'))
    return render_template('admin/category_form.html', category=cat, id=id)

@app.route('/admin/category/delete/<int:id>')
@role_required(['admin', 'manager'])
def admin_category_delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Categories WHERE Id=%s", (id,))
        conn.commit()
        flash('Категория удалена', 'success')
    except:
        flash('Нельзя удалить категорию, в которой есть товары', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin_categories'))

# Управление товарами
@app.route('/admin/products')
@role_required(['admin', 'manager'])
def admin_products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.Id, p.Name, p.Price, p.QuantityInStock, c.Name as CategoryName, p.Manufacturer, p.Code
        FROM Products p
        LEFT JOIN Categories c ON p.CategoryId = c.Id
        ORDER BY p.Id
    """)
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/products.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@role_required(['admin', 'manager'])
def admin_product_add():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT Id, Name FROM Categories ORDER BY Name")
    categories = cur.fetchall()
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        category_id = request.form.get('category_id') or None
        manufacturer = request.form['manufacturer']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        description = request.form['description']
        image_url = request.form.get('image_url', '')
        cur.execute("""
            INSERT INTO Products (Code, Name, CategoryId, Manufacturer, Price, QuantityInStock, Description, ImageUrl)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (code, name, category_id, manufacturer, price, quantity, description, image_url))
        conn.commit()
        flash('Товар добавлен', 'success')
        return redirect(url_for('admin_products'))
    cur.close()
    conn.close()
    return render_template('admin/product_form.html', categories=categories)

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
@role_required(['admin', 'manager'])
def admin_product_edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        category_id = request.form.get('category_id') or None
        manufacturer = request.form['manufacturer']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        description = request.form['description']
        image_url = request.form.get('image_url', '')
        cur.execute("""
            UPDATE Products
            SET Code=%s, Name=%s, CategoryId=%s, Manufacturer=%s, Price=%s, QuantityInStock=%s, Description=%s, ImageUrl=%s
            WHERE Id=%s
        """, (code, name, category_id, manufacturer, price, quantity, description, image_url, id))
        conn.commit()
        flash('Товар обновлён', 'success')
        return redirect(url_for('admin_products'))
    cur.execute("SELECT * FROM Products WHERE Id=%s", (id,))
    product = cur.fetchone()
    cur.execute("SELECT Id, Name FROM Categories ORDER BY Name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    if not product:
        flash('Товар не найден', 'danger')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', product=product, categories=categories, edit=True)

@app.route('/admin/product/delete/<int:id>')
@role_required(['admin', 'manager'])
def admin_product_delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Products WHERE Id=%s", (id,))
        conn.commit()
        flash('Товар удалён', 'success')
    except:
        flash('Нельзя удалить товар, связанный с заказами', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('admin_products'))

# Управление заказами для менеджера/админа
@app.route('/admin/orders')
@role_required(['admin', 'manager'])
def admin_orders():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.Id, o.OrderDate, o.Status, o.TotalPrice, c.FullName
        FROM Orders o
        JOIN Clients c ON o.ClientId = c.Id
        ORDER BY o.OrderDate DESC
    """)
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/order/status/<int:order_id>', methods=['POST'])
@role_required(['admin', 'manager'])
def admin_order_status(order_id):
    new_status = request.form['status']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE Orders SET Status=%s WHERE Id=%s", (new_status, order_id))
    conn.commit()
    cur.close()
    conn.close()
    flash('Статус заказа обновлён', 'success')
    return redirect(url_for('admin_orders'))

# ---------- Отчёты (только admin/manager) ----------
@app.route('/reports')
@role_required(['admin', 'manager'])
def reports():
    return render_template('reports.html')

@app.route('/reports/sales')
@role_required(['admin', 'manager'])
def reports_sales():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    conn = get_db_connection()
    cur = conn.cursor()
    if start_date and end_date:
        cur.execute("""
            SELECT SUM(TotalPrice) as total_sales, COUNT(*) as order_count
            FROM Orders
            WHERE OrderDate BETWEEN %s AND %s
        """, (start_date, end_date))
        data = cur.fetchone()
        total_sales = data[0] if data[0] else 0
        order_count = data[1] if data[1] else 0
    else:
        total_sales = None
        order_count = None
    cur.close()
    conn.close()
    return render_template('reports_sales.html', start_date=start_date, end_date=end_date,
                           total_sales=total_sales, order_count=order_count)

@app.route('/reports/popular')
@role_required(['admin', 'manager'])
def reports_popular():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.Name, SUM(oi.Quantity) as total_sold
        FROM OrderItems oi
        JOIN Products p ON oi.ProductId = p.Id
        GROUP BY p.Id
        ORDER BY total_sold DESC
        LIMIT 10
    """)
    popular = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('reports_popular.html', popular=popular)

# ---------- Запуск приложения ----------
if __name__ == '__main__':
    app.run(debug=True)